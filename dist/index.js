import "dotenv/config";
import { getStravaConfig } from "./config.js";
import { StravaClient } from "./strava-client.js";
async function main() {
    const { accessToken } = getStravaConfig();
    const client = new StravaClient(accessToken);
    console.log("Strava Test - fetching athlete profile...\n");
    const athlete = await client.getAthlete();
    console.log(`Athlete: ${athlete.firstname} ${athlete.lastname} (@${athlete.username ?? "n/a"})`);
    if (athlete.city || athlete.country) {
        console.log(`Location: ${[athlete.city, athlete.country].filter(Boolean).join(", ")}`);
    }
    console.log("\nRecent activities:");
    const activities = await client.getActivities(1, 5);
    if (activities.length === 0) {
        console.log("  (none)");
        return;
    }
    for (const activity of activities) {
        const a = activity;
        const km = a.distance != null ? (a.distance / 1000).toFixed(2) : "?";
        console.log(`  - ${a.name ?? "Unnamed"} (${a.type ?? "?"}) - ${km} km`);
    }
}
main().catch((error) => {
    const message = error instanceof Error ? error.message : String(error);
    console.error("\nError:", message);
    console.error("\nCopy .env.example to .env and add your Strava API credentials.");
    process.exit(1);
});
