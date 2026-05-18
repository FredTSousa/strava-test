const STRAVA_API = "https://www.strava.com/api/v3";

export type Athlete = {
  id: number;
  username: string | null;
  firstname: string;
  lastname: string;
  city: string | null;
  country: string | null;
};

export class StravaClient {
  constructor(private readonly accessToken: string) {}

  private async request<T>(path: string): Promise<T> {
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

    return response.json() as Promise<T>;
  }

  getAthlete() {
    return this.request<Athlete>("/athlete");
  }

  getActivities(page = 1, perPage = 5) {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    });
    return this.request<unknown[]>(`/athlete/activities?${params}`);
  }
}