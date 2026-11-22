// Application de bureau de la plateforme éducative (Windows, Mac, Linux).
// Une fenêtre qui ouvre le site en ligne : mêmes comptes, mêmes contenus, mises à jour sans rien réinstaller
// (le site change, l'application suit). Rien n'est envoyé ailleurs que sur le site, ses labos et son serveur.
"use strict";
const { app, BrowserWindow, Menu, session, shell } = require("electron");
const path = require("path");

const SITE = "https://nikaisedoua-source.github.io/plateforme-educative-public/";
// Adresses du site : la page, les labos (même domaine) et le serveur (relais Vercel puis Render).
const ORIGINES_SITE = new Set([
  "https://nikaisedoua-source.github.io",
  "https://plateforme-educative-relais.vercel.app",
  "https://plateforme-educative-api.onrender.com",
]);
// Repère lu par le site pour masquer « Télécharger l'application » dans l'application elle-même.
const MARQUE = "PlateformeEducativeBureau/" + app.getVersion();

app.setName("Plateforme éducative");
if (!app.requestSingleInstanceLock()) app.quit();

function origine(url) {
  try { return new URL(url).origin; } catch { return ""; }
}

function estDuSite(url) {
  return ORIGINES_SITE.has(origine(url));
}

function horsLigne(fenetre) {
  fenetre.loadFile(path.join(__dirname, "hors-ligne.html"));
}

function menuContextuel(fenetre) {
  fenetre.webContents.on("context-menu", (_event, p) => {
    const elements = [];
    if (p.isEditable) {
      elements.push({ role: "undo", label: "Annuler" }, { role: "redo", label: "Rétablir" }, { type: "separator" },
        { role: "cut", label: "Couper" }, { role: "copy", label: "Copier" }, { role: "paste", label: "Coller" },
        { role: "selectAll", label: "Tout sélectionner" });
    } else if (p.selectionText) {
      elements.push({ role: "copy", label: "Copier" });
    }
    if (p.misspelledWord && p.dictionarySuggestions.length) {
      elements.unshift(...p.dictionarySuggestions.slice(0, 4).map((mot) => ({
        label: mot, click: () => fenetre.webContents.replaceMisspelling(mot),
      })), { type: "separator" });
    }
    if (elements.length) Menu.buildFromTemplate(elements).popup({ window: fenetre });
  });
}

function reglerFenetre(fenetre) {
  const contenu = fenetre.webContents;
  contenu.setUserAgent(contenu.getUserAgent() + " " + MARQUE);
  // Nouvelle fenêtre demandée par le site (labo en grand, document…) : elle reste dans l'application.
  contenu.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("https://") || url.startsWith("blob:") || url === "about:blank") {
      return { action: "allow", overrideBrowserWindowOptions: optionsFenetre() };
    }
    if (url.startsWith("mailto:") || url.startsWith("tel:")) shell.openExternal(url);
    return { action: "deny" };
  });
  contenu.on("did-create-window", (enfant) => reglerFenetre(enfant));
  // Seules les adresses https restent dans la fenêtre (connexion Google/GitHub comprise).
  contenu.on("will-navigate", (event, url) => {
    if (url.startsWith("https://") || url.startsWith("file://")) return;
    event.preventDefault();
    if (url.startsWith("mailto:") || url.startsWith("tel:")) shell.openExternal(url);
  });
  contenu.on("did-fail-load", (_event, code, _description, url, principal) => {
    // -3 : chargement remplacé par un autre (normal) ; seule la page principale du site compte.
    if (principal && code !== -3 && estDuSite(url)) horsLigne(fenetre);
  });
  menuContextuel(fenetre);
}

function optionsFenetre() {
  return {
    width: 1280,
    height: 860,
    minWidth: 360,
    minHeight: 500,
    backgroundColor: "#F5F7FC",
    title: "Plateforme éducative",
    icon: path.join(__dirname, "icone.png"),
    autoHideMenuBar: true,
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true, spellcheck: true },
  };
}

function ouvrir() {
  const fenetre = new BrowserWindow({ ...optionsFenetre(), show: false });
  reglerFenetre(fenetre);
  fenetre.once("ready-to-show", () => fenetre.show());
  fenetre.loadURL(SITE).catch(() => horsLigne(fenetre));
  return fenetre;
}

function menuPrincipal() {
  const mac = process.platform === "darwin";
  const modele = [
    ...(mac ? [{ label: app.name, submenu: [
      { role: "about", label: "À propos de Plateforme éducative" }, { type: "separator" },
      { role: "hide", label: "Masquer" }, { role: "hideOthers", label: "Masquer les autres" }, { type: "separator" },
      { role: "quit", label: "Quitter" },
    ] }] : []),
    { label: "Édition", submenu: [
      { role: "undo", label: "Annuler" }, { role: "redo", label: "Rétablir" }, { type: "separator" },
      { role: "cut", label: "Couper" }, { role: "copy", label: "Copier" }, { role: "paste", label: "Coller" },
      { role: "selectAll", label: "Tout sélectionner" },
    ] },
    { label: "Affichage", submenu: [
      { label: "Accueil du site", accelerator: "CmdOrCtrl+Shift+H",
        click: (_item, fenetre) => fenetre && fenetre.loadURL(SITE) },
      { role: "reload", label: "Recharger" }, { type: "separator" },
      { role: "resetZoom", label: "Taille normale" }, { role: "zoomIn", label: "Agrandir" },
      { role: "zoomOut", label: "Réduire" }, { type: "separator" },
      { role: "togglefullscreen", label: "Plein écran" },
    ] },
    { label: "Fenêtre", submenu: [
      { role: "minimize", label: "Réduire dans le Dock" },
      ...(mac ? [{ role: "zoom", label: "Agrandir la fenêtre" }] : [{ role: "close", label: "Fermer" }]),
    ] },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(modele));
}

app.on("second-instance", () => {
  const fenetre = BrowserWindow.getAllWindows()[0];
  if (fenetre) { if (fenetre.isMinimized()) fenetre.restore(); fenetre.focus(); }
});

app.whenReady().then(() => {
  // Micro, caméra, plein écran, presse-papiers : seulement pour le site lui-même.
  const autorises = new Set(["media", "fullscreen", "clipboard-sanitized-write", "clipboard-read", "speaker-selection"]);
  session.defaultSession.setPermissionRequestHandler((contenu, permission, repondre, details) => {
    repondre(autorises.has(permission) && estDuSite(details.requestingUrl || contenu.getURL()));
  });
  session.defaultSession.setSpellCheckerLanguages(["fr", "en-US"].filter(
    (langue) => session.defaultSession.availableSpellCheckerLanguages.includes(langue)));
  menuPrincipal();
  ouvrir();
  app.on("activate", () => { if (BrowserWindow.getAllWindows().length === 0) ouvrir(); });
});

app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });
