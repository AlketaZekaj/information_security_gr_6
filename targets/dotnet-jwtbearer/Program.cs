using System.Security.Cryptography;
using System.Text.Json;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;

var builder = WebApplication.CreateBuilder(args);

var mode = Environment.GetEnvironmentVariable("CONFIG_MODE") ?? "default";
if (mode is not ("default" or "hardened"))
{
    throw new InvalidOperationException("CONFIG_MODE must be 'default' or 'hardened'.");
}

var policyPath = Environment.GetEnvironmentVariable("POLICY") ?? "/policy/policy.json";
var publicKeyPath = Environment.GetEnvironmentVariable("KEYS_PUB") ?? "/keys/public.pem";

using var policyDocument = JsonDocument.Parse(File.ReadAllText(policyPath));
var policy = policyDocument.RootElement;
var issuer = policy.GetProperty("issuer").GetString()
    ?? throw new InvalidOperationException("policy.json issuer is missing.");
var audience = policy.GetProperty("audience").GetString()
    ?? throw new InvalidOperationException("policy.json audience is missing.");

using var rsa = RSA.Create();
rsa.ImportFromPem(File.ReadAllText(publicKeyPath));
var key = new RsaSecurityKey(rsa);

var tokenValidationParameters = new TokenValidationParameters
{
    IssuerSigningKey = key,
    ValidIssuer = issuer,
    ValidAudience = audience
};

if (mode == "hardened")
{
    tokenValidationParameters.ValidateIssuer = true;
    tokenValidationParameters.ValidateAudience = true;
    tokenValidationParameters.ValidateLifetime = true;
    tokenValidationParameters.ValidateIssuerSigningKey = true;
    tokenValidationParameters.RequireSignedTokens = true;
    tokenValidationParameters.RequireExpirationTime = true;
    tokenValidationParameters.ValidAlgorithms = new[] { SecurityAlgorithms.RsaSha256 };
    tokenValidationParameters.ClockSkew = TimeSpan.Zero;
}

Console.WriteLine($"JwtBearer target starting in CONFIG_MODE={mode}");

builder.Services
    .AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        // Official quick-start/default reference:
        // https://learn.microsoft.com/en-us/aspnet/core/security/authentication/configure-jwt-bearer-authentication
        options.TokenValidationParameters = tokenValidationParameters;
    });
builder.Services.AddAuthorization();

var app = builder.Build();
app.UseAuthentication();
app.UseAuthorization();
app.MapGet("/health", () => Results.Ok("ok"));
app.MapGet("/protected", () => Results.Ok("ok")).RequireAuthorization();
app.Run();
