import { loadOpportunitiesResult } from "@/lib/airtable";
import { OpportunityList } from "@/app/opportunity-list";
import { SubscribeForm } from "@/app/subscribe-form";

export const revalidate = 3600;

export default async function Home() {
  const { items: opportunities, degraded } = await loadOpportunitiesResult();
  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-bold">AI Safety Opportunities</h1>
        <p className="text-gray-600">
          Jobs, fellowships, grants, events, and courses in AI safety.{" "}
          <a href="/feed.xml" className="underline">RSS</a>
        </p>
        <div className="mt-4">
          <SubscribeForm />
        </div>
      </header>
      {degraded && (
        <p className="mb-4 rounded border border-amber-400 bg-amber-50 p-3 text-sm text-amber-900">
          Listings are temporarily unavailable — the data source could not be reached. Please
          check back soon.
        </p>
      )}
      <OpportunityList opportunities={opportunities} nowISO={new Date().toISOString()} />
      <footer className="mt-12 text-sm text-gray-500">
        <a href="/privacy" className="underline">Privacy</a>
        {" · "}
        <a href="/terms" className="underline">Terms</a>
      </footer>
    </main>
  );
}
