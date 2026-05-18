import "dotenv/config";

const clientId = process.env.STRAVA_CLIENT_ID?.trim();
const redirectUri =
  process.env.STRAVA_REDIRECT_URI?.trim() || "http://localhost";

if (!clientId) {
  console.error("Set STRAVA_CLIENT_ID in .env (see .env.example)");
  process.exit(1);
}

const params = new URLSearchParams({
  client_id: clientId,
  response_type: "code",
  redirect_uri: redirectUri,
  approval_prompt: "auto",
  scope: "read,activity:read",
});

const url = `https://www.strava.com/oauth/authorize?${params}`;

console.log("\nOpen this URL in your browser, approve access, then copy the ?code= from the redirect:\n");
console.log(url);
console.log(
  "\nExchange the code for tokens at https://developers.strava.com/docs/authentication/\n"
);