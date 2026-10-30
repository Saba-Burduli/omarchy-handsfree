// What the edit shows, by clip number from commands.txt. Timing and zooms come
// from the take's command log (src/take.json, made by scripts/prep.mjs).
export const config = {
  // The first thing on screen, before any text.
  hook: "02",
  // Right after the hook.
  title: ["Control Omarchy", "with your voice."],
  // Clips in the order they play after the title (the hook isn't repeated).
  order: ["04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19"],
  // Montage clips: just the command and a quick look at the result.
  fast: ["07", "08", "12", "13", "14", "16", "17", "18", "19"],
  // Extra seconds on a result worth looking at.
  hold: { "02": 1.6, "05": 1.0, "06": 0.4, "09": 0.4, "11": 0.5, "15": 0.3 } as Record<string, number>,
  // Small chip that appears when a section starts.
  sections: { "04": "Apps", "09": "The web", "12": "Hands-free, everything" } as Record<string, string>,
  name: "Omarchy Hands-Free",
  tagline: "Voice + eye control for Omarchy. Runs offline.",
  repo: "github.com/Saba-Burduli/omarchy-handsfree",
  install: ["git clone https://github.com/Saba-Burduli/omarchy-handsfree", "cd omarchy-handsfree && ./install.sh"],
  keys: ["Super", "Alt", "V"],
};

export const theme = {
  bg: "#0d0f12",
  panel: "#161a20",
  text: "#f2f4f8",
  dim: "#8b93a1",
  accent: "#7aa2f7", // tokyo-night blue, Omarchy's default palette
  ok: "#9ece6a",
};
