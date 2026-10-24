using System.Security.Cryptography;
using System.Text.Json;
using Microsoft.IdentityModel.JsonWebTokens;
using Microsoft.IdentityModel.Tokens;

var builder = WebApplication.CreateBuilder(args);

var mode = Environment.GetEnvironmentVariable("CONFIG_MODE") ?? "default";
if (mode is not ("default" or "hardened"))
{
    throw new InvalidOperationException("CONFIG_MODE must be 'default' or 'hardened'.");
}

using var policyDocument = JsonDocument.Parse(File.ReadAllText("/policy/policy.json"));
var policy = policyDocument.RootElement;
var issuer = policy.GetProperty("issuer").GetString()
    ?? throw new InvalidOperationException("policy.json issuer is missing.");
var audience = policy.GetProperty("audience").GetString()
    ?? throw new InvalidOperationException("policy.json audience is missing.");

using var rsa = RSA.Create();
rsa.ImportFromPem(File.ReadAllText("/keys/public.pem"));
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

var handler = new JsonWebTokenHandler();
Console.WriteLine($"JsonWebTokenHandler target starting in CONFIG_MODE={mode}");

var app = builder.Build();
app.MapGet("/health", () => Results.Ok("ok"));
app.MapGet("/protected", async (HttpContext context) =>
{
    var authorization = context.Request.Headers.Authorization.ToString();
    if (!authorization.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase))
    {
        context.Response.Headers["X-Reject-Reason"] = "MissingBearer";
        return Results.StatusCode(StatusCodes.Status401Unauthorized);
    }

    var token = authorization["Bearer ".Length..].Trim();
    var result = await handler.ValidateTokenAsync(token, tokenValidationParameters);
    if (result.IsValid)
    {
        return Results.Ok("ok");
    }

    context.Response.Headers["X-Reject-Reason"] = result.Exception?.GetType().Name ?? "TokenValidationFailed";
    return Results.StatusCode(StatusCodes.Status401Unauthorized);
});
app.Run();
