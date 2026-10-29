// Minimal protected API validating JWTs with golang-jwt.
//
// Default mode follows the golang-jwt documentation for parsing (jwt.Parse with a key function):
// https://golang-jwt.github.io/jwt/usage/parse/
// See CONFIG_NOTES.md for every line that differs between the two modes.
package main

import (
	"crypto/rsa"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"regexp"
	"runtime/debug"
	"slices"
	"strconv"
	"strings"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

type policy struct {
	Issuer            string   `json:"issuer"`
	Audience          string   `json:"audience"`
	AllowedAlgorithms []string `json:"allowed_algorithms"`
	RequiredClaims    []string `json:"required_claims"`
	ClockSkewSeconds  int      `json:"clock_skew_seconds"`
}

var (
	mode      = envOr("CONFIG_MODE", "default")
	publicKey *rsa.PublicKey
	pol       policy
	version   = libraryVersion()
	bearer    = regexp.MustCompile(`(?i)^Bearer\s+(.+)$`)
)

func envOr(name, fallback string) string {
	if value := os.Getenv(name); value != "" {
		return value
	}
	return fallback
}

func libraryVersion() string {
	if info, ok := debug.ReadBuildInfo(); ok {
		for _, dep := range info.Deps {
			if dep.Path == "github.com/golang-jwt/jwt/v5" {
				return strings.TrimPrefix(dep.Version, "v")
			}
		}
	}
	return "unknown"
}

func keyFunc(*jwt.Token) (any, error) {
	return publicKey, nil
}

func validateDefault(token string) error {
	_, err := jwt.Parse(token, keyFunc)
	return err
}

func validateHardened(token string) error {
	options := []jwt.ParserOption{
		jwt.WithValidMethods(pol.AllowedAlgorithms),
		jwt.WithIssuer(pol.Issuer),
		jwt.WithAudience(pol.Audience),
		jwt.WithLeeway(time.Duration(pol.ClockSkewSeconds) * time.Second),
	}
	// exp is checked only when present unless this option is passed.
	if slices.Contains(pol.RequiredClaims, "exp") {
		options = append(options, jwt.WithExpirationRequired())
	}
	_, err := jwt.Parse(token, keyFunc, options...)
	return err
}

// oneLine keeps a header value on one line of printable ASCII.
func oneLine(text string) string {
	return strings.Map(func(r rune) rune {
		if r < 0x20 || r > 0x7e {
			return '?'
		}
		return r
	}, text)
}

func respond(w http.ResponseWriter, status int, body, contentType, reason string) {
	w.Header().Set("Content-Type", contentType)
	w.Header().Set("Content-Length", strconv.Itoa(len(body)))
	if reason != "" {
		w.Header().Set("X-Reject-Reason", oneLine(reason))
	}
	w.WriteHeader(status)
	_, _ = w.Write([]byte(body))
}

func handler(validate func(string) error) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			respond(w, http.StatusMethodNotAllowed, "method not allowed", "text/plain", "")
			return
		}
		switch r.URL.Path {
		case "/health":
			body, _ := json.Marshal(map[string]string{
				"status": "ok", "component": "golang-jwt", "version": version, "config": mode,
			})
			respond(w, http.StatusOK, string(body), "application/json", "")
		case "/protected":
			match := bearer.FindStringSubmatch(r.Header.Get("Authorization"))
			if match == nil {
				respond(w, http.StatusUnauthorized, "unauthorized", "text/plain", "MissingBearer")
				return
			}
			// The key function cannot fail, so every error from Parse is a validation decision.
			if err := validate(strings.TrimSpace(match[1])); err != nil {
				respond(w, http.StatusUnauthorized, "unauthorized", "text/plain", err.Error())
				return
			}
			respond(w, http.StatusOK, "ok", "text/plain", "")
		default:
			respond(w, http.StatusNotFound, "not found", "text/plain", "")
		}
	}
}

// healthcheck lets the container check itself: the final image has no shell or curl.
func healthcheck() int {
	client := http.Client{Timeout: 2 * time.Second}
	response, err := client.Get("http://127.0.0.1:8080/health")
	if err != nil {
		return 1
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return 1
	}
	return 0
}

func main() {
	if len(os.Args) > 1 && os.Args[1] == "-healthcheck" {
		os.Exit(healthcheck())
	}
	if mode != "default" && mode != "hardened" {
		log.Fatal("CONFIG_MODE must be 'default' or 'hardened'")
	}

	pem, err := os.ReadFile(envOr("KEYS_PUB", "/keys/public.pem"))
	if err != nil {
		log.Fatal(err)
	}
	if publicKey, err = jwt.ParseRSAPublicKeyFromPEM(pem); err != nil {
		log.Fatal(err)
	}
	raw, err := os.ReadFile(envOr("POLICY", "/policy/policy.json"))
	if err != nil {
		log.Fatal(err)
	}
	if err = json.Unmarshal(raw, &pol); err != nil {
		log.Fatal(err)
	}

	validate := validateDefault
	if mode == "hardened" {
		validate = validateHardened
	}
	server := &http.Server{
		Addr:              "0.0.0.0:8080",
		Handler:           handler(validate),
		ReadHeaderTimeout: 5 * time.Second,
	}
	log.Printf("golang-jwt %s listening on :8080 (CONFIG_MODE=%s)", version, mode)
	log.Fatal(server.ListenAndServe())
}
