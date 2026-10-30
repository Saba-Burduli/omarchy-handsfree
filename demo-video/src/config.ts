// What the edit shows, by clip number from commands.txt. Timing and zooms come
// from the take's command log (src/take.json, made by scripts/prep.mjs).
export const config = {
  // The first thing on screen, before any text.
  hook: "02",
  // Clips in the order they play after the intro (the hook isn't repeated).
  order: ["04", "05", "06", "09", "10", "11", "12", "13", "14", "15", "16", "18", "19"],
  // Montage clips: the command and a shorter look at the result.
  fast: ["12", "13", "14", "16", "18", "19"],
  // Extra seconds on a result worth looking at.
  hold: { "02": 1.4, "05": 1.2, "06": 0.5, "09": 0.4, "11": 0.6, "15": 0.4 } as Record<string, number>,
  // Where a section starts: a chip on screen and a narrator line (narration.json)
  // spoken over the end of the previous result.
  sections: {
    "04": { label: "Apps", vo: "apps" },
    "09": { label: "The web", vo: "web" },
    "12": { label: "Hands-free, everything", vo: "more" },
  } as Record<string, { label: string; vo: string }>,
  // Intro cards, timed (seconds) to the phrases of narration.json "intro".
  intro: {
    name: 0,
    line: { at: 1.95, words: ["Control", "your", "entire", "desktop", "with", "just", "your", "voice."] },
    chips: [
      { at: 5.4, text: "Apps" },
      { at: 6.05, text: "Commands" },
      { at: 6.9, text: "The web" },
      { at: 7.65, text: "All hands-free" },
    ],
    offline: 8.55,
  },
  name: "Omarchy Hands-Free",
  tagline: "Voice + eye control for Omarchy. Runs offline.",
  repo: "github.com/Saba-Burduli/omarchy-handsfree",
  install: ["git clone https://github.com/Saba-Burduli/omarchy-handsfree", "cd omarchy-handsfree && ./install.sh"],
  keys: ["Super", "Alt", "V"],
  // Outro beats (seconds from the outro start), timed to narration.json "outro".
  outro: { keys: 2.7, repo: 3.6, footer: 4.4 },
};

export const theme = {
  bg: "#0d0f12",
  panel: "#161a20",
  text: "#f2f4f8",
  dim: "#8b93a1",
  accent: "#7aa2f7", // tokyo-night blue, Omarchy's default palette
  ok: "#9ece6a",
};
