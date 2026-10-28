package jwtstudy;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.interfaces.RSAPublicKey;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Objects;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.json.JsonParserFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.core.SpringSecurityCoreVersion;
import org.springframework.security.oauth2.core.DelegatingOAuth2TokenValidator;
import org.springframework.security.oauth2.core.OAuth2TokenValidator;
import org.springframework.security.oauth2.jose.jws.SignatureAlgorithm;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtClaimNames;
import org.springframework.security.oauth2.jwt.JwtClaimValidator;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtIssuerValidator;
import org.springframework.security.oauth2.jwt.JwtTimestampValidator;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@SpringBootApplication
public class Application {

    static final String MODE = System.getenv().getOrDefault("CONFIG_MODE", "default");

    public static void main(String[] args) {
        if (!MODE.equals("default") && !MODE.equals("hardened")) {
            System.err.println("CONFIG_MODE must be 'default' or 'hardened'");
            System.exit(1);
        }
        System.out.println("spring-security " + SpringSecurityCoreVersion.getVersion()
                + " listening on :8080 (CONFIG_MODE=" + MODE + ")");
        SpringApplication.run(Application.class, args);
    }

    // Default follows the Spring Security reference: the key comes from the
    // public-key-location property (application.properties) and the filter chain is the
    // minimal resource-server configuration, plus a permitted /health for the API contract.
    // https://docs.spring.io/spring-security/reference/servlet/oauth2/resource-server/jwt.html
    @Bean
    SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
            .authorizeHttpRequests(authorize -> authorize
                .requestMatchers("/health").permitAll()
                .anyRequest().authenticated())
            .oauth2ResourceServer(oauth2 -> oauth2.jwt(Customizer.withDefaults()));
        return http.build();
    }

    // Hardened only: replaces Spring Boot's decoder. Every setting below is one row in
    // CONFIG_NOTES.md.
    @Bean
    @ConditionalOnProperty(name = "study.config-mode", havingValue = "hardened")
    JwtDecoder hardenedJwtDecoder(
            @Value("${spring.security.oauth2.resourceserver.jwt.public-key-location}") RSAPublicKey key)
            throws IOException {
        Path policyPath = Path.of(System.getenv().getOrDefault("POLICY", "/policy/policy.json"));
        Map<String, Object> policy = JsonParserFactory.getJsonParser().parseMap(Files.readString(policyPath));
        List<?> algorithms = (List<?>) policy.get("allowed_algorithms");
        if (algorithms.size() != 1) {
            throw new IllegalStateException("the NimbusJwtDecoder public-key builder takes exactly one algorithm");
        }
        String issuer = (String) policy.get("issuer");
        String audience = (String) policy.get("audience");
        long clockSkew = ((Number) policy.get("clock_skew_seconds")).longValue();

        NimbusJwtDecoder decoder = NimbusJwtDecoder.withPublicKey(key)
                .signatureAlgorithm(SignatureAlgorithm.from((String) algorithms.get(0)))
                .build();
        List<OAuth2TokenValidator<Jwt>> validators = new ArrayList<>();
        validators.add(new JwtTimestampValidator(Duration.ofSeconds(clockSkew)));
        validators.add(new JwtIssuerValidator(issuer));
        validators.add(new JwtClaimValidator<List<String>>(JwtClaimNames.AUD,
                aud -> aud != null && aud.contains(audience)));
        // JwtTimestampValidator only checks exp when it is present, so presence is checked here.
        for (Object claim : (List<?>) policy.get("required_claims")) {
            validators.add(new JwtClaimValidator<Object>((String) claim, Objects::nonNull));
        }
        decoder.setJwtValidator(new DelegatingOAuth2TokenValidator<>(validators));
        return decoder;
    }

    @RestController
    static class Endpoints {

        @GetMapping("/health")
        Map<String, String> health() {
            return Map.of("status", "ok", "component", "spring-security",
                    "version", SpringSecurityCoreVersion.getVersion(), "config", MODE);
        }

        @GetMapping("/protected")
        String protectedResource() {
            return "ok";
        }
    }
}
