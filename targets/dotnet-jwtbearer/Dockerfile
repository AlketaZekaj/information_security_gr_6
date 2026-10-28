# SDK 8.0.427
FROM mcr.microsoft.com/dotnet/sdk:8.0@sha256:6ba9644da07bb5b560a402acec9ca38711a0762969f1b61da261df5c9f6f85da AS build
WORKDIR /src
COPY dotnet-jwtbearer.csproj Program.cs ./
# Downloaded NuGet packages persist in a build cache between builds, outside the image.
RUN --mount=type=cache,target=/root/.nuget/packages dotnet publish -c Release -o /app/publish

# ASP.NET Core runtime 8.0.33
FROM mcr.microsoft.com/dotnet/aspnet:8.0@sha256:ea721098d6ea2894ff9bd8387821a1659d4765d6c014b8d648bb1da16f016f5a AS final
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV ASPNETCORE_URLS=http://+:8080
COPY --from=build /app/publish .
EXPOSE 8080
ENTRYPOINT ["dotnet", "dotnet-jwtbearer.dll"]
