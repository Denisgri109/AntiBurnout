(() => {
  const savedTheme = localStorage.getItem("theme");
  const systemTheme = window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
  const initialTheme = savedTheme === "light" || savedTheme === "dark"
    ? savedTheme
    : systemTheme;

  document.documentElement.setAttribute("data-theme", initialTheme);

  const toggleButton = document.getElementById("theme-toggle");
  const themeIcon = document.getElementById("theme-icon");
  const themeLabel = document.getElementById("theme-label");

  if (toggleButton && themeIcon && themeLabel) {
    const applyTheme = (theme) => {
      const isDark = theme === "dark";

      document.documentElement.setAttribute("data-theme", theme);
      localStorage.setItem("theme", theme);
      themeIcon.textContent = isDark ? "☀" : "☾";
      themeLabel.textContent = isDark ? "Light mode" : "Dark mode";
      toggleButton.setAttribute(
        "aria-label",
        isDark ? "Switch to light mode" : "Switch to dark mode"
      );
    };

    applyTheme(initialTheme);

    toggleButton.addEventListener("click", () => {
      const currentTheme = document.documentElement.getAttribute("data-theme");
      applyTheme(currentTheme === "dark" ? "light" : "dark");
    });
  }

  const menuButton = document.querySelector(".menu-button");
  const navigation = document.querySelector(".main-nav");

  if (menuButton && navigation) {
    const closeMenu = () => {
      navigation.classList.remove("is-open");
      menuButton.setAttribute("aria-expanded", "false");
      menuButton.setAttribute("aria-label", "Open navigation");
    };

    menuButton.addEventListener("click", () => {
      const isOpen = navigation.classList.toggle("is-open");
      menuButton.setAttribute("aria-expanded", String(isOpen));
      menuButton.setAttribute("aria-label", isOpen ? "Close navigation" : "Open navigation");
    });

    navigation.addEventListener("click", (event) => {
      if (event.target.closest("a")) {
        closeMenu();
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeMenu();
      }
    });
  }
})();
