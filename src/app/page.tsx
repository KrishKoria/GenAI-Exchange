import { Dashboard } from "@/sections/Dashboard";
import { LanguageProvider } from "@/contexts/LanguageContext";

export default function Home() {
  return (
    <LanguageProvider>
      <Dashboard />
    </LanguageProvider>
  );
}
