import 'package:material_ui/material_ui.dart';

import 'api_client.dart';

class LibraryAdmin extends StatelessWidget {
  const LibraryAdmin({super.key, required this.api, required this.onSignOut});

  final ApiClient api;
  final VoidCallback onSignOut;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Bibliothèque documentaire'),
        leading: IconButton(
          tooltip: 'Retour',
          onPressed: () => Navigator.of(context).maybePop(),
          icon: const Icon(Icons.arrow_back_rounded),
        ),
        actions: [
          TextButton.icon(
            onPressed: onSignOut,
            icon: const Icon(Icons.logout_rounded),
            label: const Text('Déconnexion'),
          ),
        ],
      ),
      body: const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text(
            'La bibliothèque documentaire est disponible dans la version Web.',
            textAlign: TextAlign.center,
          ),
        ),
      ),
    );
  }
}
