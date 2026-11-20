import 'package:material_ui/material_ui.dart';

import 'admin_dashboard.dart';
import 'api_client.dart';
import 'parcours_picker.dart';
import 'student_home.dart';
import 'theme.dart';

class AuthPage extends StatefulWidget {
  const AuthPage({super.key, required this.api});

  final ApiClient api;

  @override
  State<AuthPage> createState() => _AuthPageState();
}

class _AuthPageState extends State<AuthPage> {
  final _formKey = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _pseudo = TextEditingController();
  final _password = TextEditingController();
  final _confirmation = TextEditingController();
  bool _registering = false;
  bool _busy = false;
  String? _error;
  String? _success;
  Map<String, dynamic>? _user;
  Map<String, List<Map<String, dynamic>>>? _catalog;
  String? _catalogError;
  ParcoursSelection _parcours = const ParcoursSelection();

  @override
  void dispose() {
    _email.dispose();
    _pseudo.dispose();
    _password.dispose();
    _confirmation.dispose();
    super.dispose();
  }

  void _toggleMode() {
    setState(() {
      _registering = !_registering;
      _error = null;
      _success = null;
    });
    _password.clear();
    _confirmation.clear();
    if (_registering) _loadCatalog();
  }

  Future<void> _loadCatalog() async {
    setState(() => _catalogError = null);
    try {
      final catalog = await widget.api.catalog();
      if (mounted) setState(() => _catalog = catalog);
    } on ApiException catch (exception) {
      if (mounted) setState(() => _catalogError = exception.message);
    }
  }

  Future<void> _submit() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    setState(() {
      _busy = true;
      _error = null;
      _success = null;
    });
    try {
      if (_registering) {
        await widget.api.register(
          email: _email.text.trim(),
          password: _password.text,
          pseudo: _pseudo.text.trim(),
          gradeId: _parcours.gradeId,
          trackId: _parcours.trackId,
          classId: _parcours.classId,
        );
        final choseParcours = !_parcours.isEmpty;
        _password.clear();
        _confirmation.clear();
        if (!mounted) return;
        setState(() {
          _registering = false;
          _parcours = const ParcoursSelection();
          _success = choseParcours
              ? 'Compte créé. Votre parcours sera confirmé par l’administrateur. Vous pouvez maintenant vous connecter.'
              : 'Compte créé. Vous pouvez maintenant vous connecter.';
        });
      } else {
        await widget.api.login(
          email: _email.text.trim(),
          password: _password.text,
        );
        final user = await widget.api.currentUser();
        final role = user['role'];
        if (role != 'student' && role != 'admin') {
          throw const ApiException('Le rôle de ce compte n’est pas reconnu.');
        }
        _password.clear();
        if (!mounted) return;
        setState(() => _user = user);
      }
    } on ApiException catch (exception) {
      widget.api.logout();
      if (mounted) setState(() => _error = exception.message);
    } catch (_) {
      widget.api.logout();
      if (mounted) {
        setState(
          () => _error = 'Une erreur inattendue est survenue. Réessayez.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _signOut() {
    widget.api.logout();
    _password.clear();
    _confirmation.clear();
    setState(() {
      _user = null;
      _error = null;
      _success = null;
      _registering = false;
      _parcours = const ParcoursSelection();
    });
  }

  String? _emailValidator(String? value) {
    final email = value?.trim() ?? '';
    if (email.isEmpty) return 'Saisissez votre adresse e-mail.';
    if (!RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$').hasMatch(email)) {
      return 'Saisissez une adresse e-mail valide.';
    }
    return null;
  }

  String? _passwordValidator(String? value) {
    final password = value ?? '';
    if (password.isEmpty) return 'Saisissez votre mot de passe.';
    if (password.length > 128) return 'Le mot de passe est trop long.';
    if (_registering && password.length < 12) {
      return '12 caractères minimum.';
    }
    return null;
  }

  Widget _heroPanel() {
    return Container(
      margin: const EdgeInsets.all(24),
      padding: const EdgeInsets.all(48),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(30),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF2F5BFF), Color(0xFF6B8CFF)],
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          const Row(
            children: [
              Icon(Icons.auto_stories_rounded, color: Colors.white, size: 34),
              SizedBox(width: 12),
              Text(
                'Plateforme éducative',
                style: TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w900,
                  fontSize: 24,
                ),
              ),
            ],
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 7,
                ),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: .15),
                  borderRadius: BorderRadius.circular(99),
                ),
                child: const Text(
                  'UN ESPACE CONÇU POUR APPRENDRE',
                  style: TextStyle(
                    color: Colors.white,
                    letterSpacing: 1,
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              const SizedBox(height: 24),
              const Text(
                'Les bons repères,\nà votre rythme.',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 48,
                  height: 1.1,
                  fontWeight: FontWeight.w900,
                ),
              ),
              const SizedBox(height: 16),
              Text(
                'Un espace clair pour les élèves et un outil de configuration pour l’équipe pédagogique.',
                style: TextStyle(
                  color: Colors.white.withValues(alpha: .86),
                  fontSize: 17,
                  height: 1.6,
                ),
              ),
            ],
          ),
          const Row(
            children: [
              Icon(Icons.lock_outline_rounded, color: Colors.white70, size: 18),
              SizedBox(width: 8),
              Text(
                'Les accès sont contrôlés par le serveur.',
                style: TextStyle(color: Colors.white70, fontSize: 13),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _notice(String text, {required bool isError}) {
    final color = isError ? Brand.coral : Brand.mint;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: .08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: .3)),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: color,
          fontWeight: FontWeight.w800,
          height: 1.4,
        ),
      ),
    );
  }

  Widget _textField({
    required String label,
    required TextEditingController controller,
    required IconData icon,
    required String? Function(String?) validator,
    Key? key,
    bool obscure = false,
    TextInputType? keyboardType,
    TextCapitalization capitalization = TextCapitalization.none,
    String? helperText,
  }) {
    return ChunkCard(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      color: Colors.white,
      child: TextFormField(
        key: key,
        controller: controller,
        obscureText: obscure,
        keyboardType: keyboardType,
        textCapitalization: capitalization,
        autocorrect: !obscure,
        enableSuggestions: !obscure,
        validator: validator,
        style: const TextStyle(fontWeight: FontWeight.w800),
        decoration: InputDecoration(
          labelText: label,
          helperText: helperText,
          prefixIcon: Icon(icon, color: Brand.blue),
          border: InputBorder.none,
          focusedBorder: InputBorder.none,
          enabledBorder: InputBorder.none,
          contentPadding: const EdgeInsets.symmetric(vertical: 16),
        ),
      ),
    );
  }

  Widget _parcoursCard() {
    final catalog = _catalog;
    return ChunkCard(
      padding: const EdgeInsets.all(16),
      color: Colors.white,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Mon parcours',
            style: TextStyle(fontWeight: FontWeight.w900, fontSize: 16),
          ),
          const SizedBox(height: 4),
          const Text(
            'Votre classe sera confirmée par l’administrateur.',
            style: TextStyle(color: Color(0xFF606B80), fontSize: 13),
          ),
          const SizedBox(height: 12),
          if (_catalogError != null)
            Row(
              children: [
                Expanded(
                  child: Text(
                    _catalogError!,
                    style: const TextStyle(color: Brand.coral),
                  ),
                ),
                TextButton(
                  onPressed: _loadCatalog,
                  child: const Text('Réessayer'),
                ),
              ],
            )
          else if (catalog == null)
            const LinearProgressIndicator(minHeight: 2)
          else
            ParcoursPicker(
              catalog: catalog,
              value: _parcours,
              onChanged: (value) => setState(() => _parcours = value),
            ),
        ],
      ),
    );
  }

  Widget _authForm() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 6),
          decoration: BoxDecoration(
            color: Brand.sun.withValues(alpha: .12),
            borderRadius: BorderRadius.circular(99),
            border: Border.all(
              color: Brand.sun.withValues(alpha: .4),
              width: 1,
            ),
          ),
          child: const Text(
            'ACCÈS SÉCURISÉ',
            style: TextStyle(
              color: Brand.sunInk,
              fontSize: 11,
              fontWeight: FontWeight.w900,
              letterSpacing: 1,
            ),
          ),
        ),
        const SizedBox(height: 24),
        Text(
          _registering ? 'Créer un compte élève' : 'Bienvenue',
          style: const TextStyle(
            fontSize: 34,
            fontWeight: FontWeight.w900,
            height: 1.1,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          _registering
              ? 'Renseignez vos informations pour créer votre accès.'
              : 'Connectez-vous pour accéder à votre espace.',
          style: const TextStyle(color: Color(0xFF606B80), fontSize: 16),
        ),
        const SizedBox(height: 28),
        if (_error != null) ...[
          _notice(_error!, isError: true),
          const SizedBox(height: 16),
        ],
        if (_success != null) ...[
          _notice(_success!, isError: false),
          const SizedBox(height: 16),
        ],
        Form(
          key: _formKey,
          child: Column(
            children: [
              if (_registering) ...[
                _textField(
                  key: const ValueKey('register.pseudo'),
                  label: 'Pseudo',
                  controller: _pseudo,
                  icon: Icons.person_outline_rounded,
                  capitalization: TextCapitalization.sentences,
                  validator: (value) {
                    final pseudo = value?.trim() ?? '';
                    if (pseudo.length < 2) {
                      return 'Le pseudo doit contenir au moins 2 caractères.';
                    }
                    if (pseudo.length > 40 ||
                        !RegExp(r'^[\w .-]+$').hasMatch(pseudo)) {
                      return 'Utilisez 2 à 40 lettres, chiffres, espaces, points ou tirets.';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 14),
              ],
              _textField(
                key: const ValueKey('auth.email'),
                label: 'Adresse e-mail',
                controller: _email,
                icon: Icons.alternate_email_rounded,
                keyboardType: TextInputType.emailAddress,
                validator: _emailValidator,
              ),
              const SizedBox(height: 14),
              _textField(
                key: const ValueKey('auth.password'),
                label: 'Mot de passe',
                controller: _password,
                icon: Icons.lock_outline_rounded,
                obscure: true,
                validator: _passwordValidator,
                helperText: _registering ? '12 caractères minimum.' : null,
              ),
              if (_registering) ...[
                const SizedBox(height: 14),
                _textField(
                  key: const ValueKey('register.confirm'),
                  label: 'Confirmer le mot de passe',
                  controller: _confirmation,
                  icon: Icons.lock_reset_rounded,
                  obscure: true,
                  validator: (value) => value != _password.text
                      ? 'Les mots de passe ne correspondent pas.'
                      : null,
                ),
                const SizedBox(height: 14),
                _parcoursCard(),
              ],
              const SizedBox(height: 24),
              SizedBox(
                width: double.infinity,
                child: PressButton(
                  key: const ValueKey('auth.submit'),
                  label: _busy
                      ? '…'
                      : (_registering ? 'Créer mon compte' : 'Se connecter'),
                  primary: true,
                  onPressed: _busy ? null : _submit,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 18),
        Center(
          child: PressButton(
            key: const ValueKey('auth.toggle'),
            label: _busy
                ? '…'
                : (_registering
                      ? 'J’ai déjà un compte — me connecter'
                      : 'Pas encore de compte ? Créer un compte'),
            primary: false,
            onPressed: _busy ? null : _toggleMode,
          ),
        ),
        const SizedBox(height: 20),
        const Divider(),
        const SizedBox(height: 12),
        const Text(
          'Les activités scolaires seront visibles après leur ajout à partir des documents de la plateforme et leur validation.',
          style: TextStyle(color: Color(0xFF69758A), fontSize: 13, height: 1.5),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final signedInUser = _user;
    if (signedInUser != null) {
      if (signedInUser['role'] == 'admin') {
        return AdminDashboard(api: widget.api, onSignOut: _signOut);
      }
      return StudentHomePage(
        api: widget.api,
        user: signedInUser,
        onSignOut: _signOut,
      );
    }

    return Scaffold(
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            final wide = constraints.maxWidth >= 960;
            return Row(
              children: [
                if (wide) Expanded(flex: 5, child: _heroPanel()),
                Expanded(
                  flex: 5,
                  child: Center(
                    child: SingleChildScrollView(
                      padding: EdgeInsets.all(wide ? 48 : 24),
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 480),
                        child: _authForm(),
                      ),
                    ),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}
