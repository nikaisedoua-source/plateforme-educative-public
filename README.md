# Plateforme éducative — copie publique

- Branche `gh-pages` : le site web compilé, publié sur GitHub Pages.
- Branche `main` :
  - `.github/workflows/reveil.yml` : réveil automatique du serveur toutes les 10 minutes ;
  - `vercel.json` (et `netlify.toml`, en secours) : **relais** gratuit vers le serveur. Certains réseaux
    (fournisseurs d'accès, téléphones) ne joignent pas l'hébergeur du serveur ; ils joignent le relais, qui
    transmet chaque demande telle quelle. Aucun secret, aucune donnée n'y est gardé.

Le code du serveur, le contenu et les secrets ne sont pas dans ce dépôt public.
