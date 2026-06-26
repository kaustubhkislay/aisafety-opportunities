import { loadOpportunities } from "@/lib/airtable";
import { OpportunityList } from "@/app/opportunity-list";

export const revalidate = 3600;

export default async function Home() {
  const opportunities = await loadOpportunities();
  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-bold">AI Safety Opportunities</h1>
        <p className="text-gray-600">
          Jobs, fellowships, grants, events, and courses in AI safety.{" "}
          <a href="/feed.xml" className="underline">RSS</a>
        </p>
      </header>
      <OpportunityList opportunities={opportunities} nowISO={new Date().toISOString()} />
      <footer className="mt-12 text-sm text-gray-500">
        <a href="/privacy" className="underline">Privacy</a>
      </footer>
    </main>
  );
}
