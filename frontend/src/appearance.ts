export type UiScale = "compact" | "normal" | "large";
export type UiFont = "system" | "editorial" | "compact";

export interface AppearanceSettings {
  scale: UiScale;
  font: UiFont;
}

const STORAGE_KEY = "news-radar-appearance";

const SCALE_VALUES: Record<UiScale, string> = {
  compact: "0.9",
  normal: "1",
  large: "1.1",
};

const DEFAULTS: AppearanceSettings = {
  scale: "normal",
  font: "system",
};

export function readAppearance(): AppearanceSettings {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}") as Partial<AppearanceSettings>;
    return {
      scale: saved.scale && saved.scale in SCALE_VALUES ? saved.scale : DEFAULTS.scale,
      font: saved.font && ["system", "editorial", "compact"].includes(saved.font)
        ? saved.font
        : DEFAULTS.font,
    };
  } catch {
    return DEFAULTS;
  }
}

export function applyAppearance(settings: AppearanceSettings): void {
  document.documentElement.dataset.font = settings.font;
  document.documentElement.style.setProperty("--ui-scale", SCALE_VALUES[settings.scale]);
}

export function saveAppearance(settings: AppearanceSettings): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  applyAppearance(settings);
}

