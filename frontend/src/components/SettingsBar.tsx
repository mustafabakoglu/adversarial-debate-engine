import { useTheme, useTypingSound, type ThemeChoice } from "../useSettings";

const THEME_ICON: Record<ThemeChoice, string> = { system: "◐", light: "☀", dark: "☾" };
const THEME_TITLE: Record<ThemeChoice, string> = {
  system: "Theme: following your system",
  light: "Theme: light",
  dark: "Theme: dark",
};

const BUTTON =
  "flex size-9 items-center justify-center rounded-full border border-line bg-surface text-sm text-ink-soft transition hover:border-ink-faint hover:text-ink";

interface Props {
  sound: ReturnType<typeof useTypingSound>;
  theme: ReturnType<typeof useTheme>;
}

export function SettingsBar({ sound, theme }: Props) {
  return (
    <div className="fixed top-4 right-4 z-10 flex gap-2">
      <button
        type="button"
        onClick={sound.toggle}
        className={BUTTON}
        title={sound.enabled ? "Typing sound on" : "Typing sound off"}
        aria-label={sound.enabled ? "Turn typing sound off" : "Turn typing sound on"}
        aria-pressed={sound.enabled}
      >
        {sound.enabled ? "♪" : "✕"}
      </button>
      <button
        type="button"
        onClick={theme.cycle}
        className={BUTTON}
        title={THEME_TITLE[theme.choice]}
        aria-label={THEME_TITLE[theme.choice]}
      >
        {THEME_ICON[theme.choice]}
      </button>
    </div>
  );
}
