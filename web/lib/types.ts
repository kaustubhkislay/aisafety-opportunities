export type OppType =
  | "job" | "internship" | "fellowship" | "grant"
  | "event" | "course" | "reading-group" | "other";

export interface Opportunity {
  title: string;
  org: string;
  type: OppType | string;
  deadline: string | null;
  link: string | null;
  location: string | null;
  remote: boolean;
  sourceServer: string;
  sourceChannel: string;
  dateSeen: string | null;
  dedupKey: string;
  sourceServers: string[];
  categories: string[];
}
