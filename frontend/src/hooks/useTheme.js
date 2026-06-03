import { useState, useEffect } from "react";

/*
 * useTheme — theme state + localStorage persistence, pushed down from the App.jsx
 * shell (App.jsx decomposition, slice 1). Owns the `theme` state, the document-body
 * `data-theme` effect, and the toggle handler. Bodies + dep array moved verbatim from
 * App.jsx. Self-contained (reads/writes localStorage + document.body); App calls it with
 * no args and renders `theme` + `toggleTheme`.
 */
export function useTheme() {
  // Theme state with localStorage persistence
  const [theme, setTheme] = useState(() => {
    const savedTheme = localStorage.getItem("graider-theme");
    return savedTheme || "dark";
  });

  // Apply theme to document body
  useEffect(() => {
    document.body.setAttribute("data-theme", theme);
    localStorage.setItem("graider-theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  };

  return { theme, toggleTheme };
}
