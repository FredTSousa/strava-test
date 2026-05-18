function required(name) {
    const value = process.env[name]?.trim();
    if (!value) {
        throw new Error(`Missing environment variable: ${name}`);
    }
    return value;
}
export function getStravaConfig() {
    return {
        clientId: required("STRAVA_CLIENT_ID"),
        clientSecret: required("STRAVA_CLIENT_SECRET"),
        redirectUri: process.env.STRAVA_REDIRECT_URI?.trim() || "http://localhost",
        accessToken: required("STRAVA_ACCESS_TOKEN"),
        refreshToken: process.env.STRAVA_REFRESH_TOKEN?.trim(),
    };
}
