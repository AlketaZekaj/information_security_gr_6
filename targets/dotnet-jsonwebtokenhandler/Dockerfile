# SDK 10.0.403
FROM mcr.microsoft.com/dotnet/sdk:10.0@sha256:de4fe90a98845d75910b9769662465c84de1a934665c431279d1382b2bddc02b AS build
WORKDIR /src
COPY dotnet-jsonwebtokenhandler.csproj Program.cs ./
# Downloaded NuGet packages persist in a build cache between builds, outside the image.
RUN --mount=type=cache,target=/root/.nuget/packages dotnet publish -c Release -o /app/publish

# ASP.NET Core runtime 10.0.14
FROM mcr.microsoft.com/dotnet/aspnet:10.0@sha256:de0ee358cdd672f7017a003bed21e9ac9ed48a27c922a59b18175b6e82fa7fee AS final
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV ASPNETCORE_URLS=http://+:8080
COPY --from=build /app/publish .
EXPOSE 8080
ENTRYPOINT ["dotnet", "dotnet-jsonwebtokenhandler.dll"]
