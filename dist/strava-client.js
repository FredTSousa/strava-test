const STRAVA_API = "https://www.strava.com/api/v3";
export class StravaClient {
    accessToken;
    constructor(accessToken) {
        this.accessToken = accessToken;
    }
    async request(path) {
        const response = await fetch(`${STRAVA_API}${path}`, {
            headers: {
                Authorization: `Bearer ${this.accessToken}`,
                Accept: "application/json",
            },
        });
        if (!response.ok) {
            const body = await response.text();
            throw new Error(`Strava API ${response.status}: ${body}`);
        }
        return response.json();
    }
    getAthlete() {
        return this.request("/athlete");
    }
    getActivities(page = 1, perPage = 5) {
        const params = new URLSearchParams({
            page: String(page),
            per_page: String(perPage),
        });
        return this.request(`/athlete/activities?${params}`);
    }
}
