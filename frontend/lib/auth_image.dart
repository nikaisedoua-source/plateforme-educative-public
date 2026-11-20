import 'dart:typed_data';

import 'package:material_ui/material_ui.dart';

import 'api_client.dart';

/// Image servie par l'API avec le jeton (aperçu de page, figure recadrée).
class AuthImage extends StatefulWidget {
  const AuthImage({super.key, required this.api, required this.path, this.height});
  final ApiClient api;
  final String path;
  final double? height;

  @override
  State<AuthImage> createState() => _AuthImageState();
}

class _AuthImageState extends State<AuthImage> {
  late Future<Uint8List> _bytes = widget.api.fetchBytes(widget.path);

  @override
  void didUpdateWidget(AuthImage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.path != widget.path) _bytes = widget.api.fetchBytes(widget.path);
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<Uint8List>(
    future: _bytes,
    builder: (context, snapshot) {
      if (snapshot.hasError) {
        return SizedBox(
          height: widget.height ?? 120,
          child: Center(child: Text('Aperçu indisponible : ${snapshot.error}')),
        );
      }
      if (!snapshot.hasData) {
        return SizedBox(
          height: widget.height ?? 120,
          child: const Center(child: CircularProgressIndicator()),
        );
      }
      return Image.memory(
        snapshot.data!,
        height: widget.height,
        fit: BoxFit.contain,
        gaplessPlayback: true,
      );
    },
  );
}
