import { Button } from "@/components/ui/button";
import { Menu, BarChart3 } from "lucide-react";

export interface MobileHeaderProps {
  onOpenSidebar: () => void;
  onToggleRightPanel: () => void;
  currentDocId: string | null;
  appTitle: string;
}

/**
 * Mobile header with sidebar and analysis panel toggles
 */
export const MobileHeader = ({
  onOpenSidebar,
  onToggleRightPanel,
  currentDocId,
  appTitle,
}: MobileHeaderProps) => {
  return (
    <div className="flex w-full items-center justify-between border-b border-white/10 bg-[#111111] px-4 py-3 md:hidden shrink-0">
      <Button variant="ghost" size="icon" onClick={onOpenSidebar}>
        <Menu className="h-5 w-5" />
      </Button>
      <div className="text-base font-semibold bg-gradient-to-r from-purple-400 to-pink-500 bg-clip-text text-transparent">
        {appTitle}
      </div>
      <Button
        variant="ghost"
        size="icon"
        onClick={onToggleRightPanel}
        className={currentDocId ? "" : "opacity-50"}
        disabled={!currentDocId}
      >
        <BarChart3 className="h-5 w-5" />
      </Button>
    </div>
  );
};
