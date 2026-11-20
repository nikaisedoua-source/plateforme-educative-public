import 'dart:math' as math;

import 'package:material_ui/material_ui.dart';

import 'sounds.dart';

/// Palette douce inspirée du prototype : mêmes familles de couleurs, en pastel, contours légers et ombres
/// diffuses. Les noms sont conservés pour tous les écrans existants.
class Brand {
  static const blue = Color(0xFF5B7BF5);
  static const lilac = Color(0xFF9D8CF2);
  static const sun = Color(0xFFFFD36E);
  static const coral = Color(0xFFFF8F84);
  static const mint = Color(0xFF4CC495);
  static const sky = Color(0xFF7CC6F2);
  static const peach = Color(0xFFFFE6D6);
  static const sunInk = Color(0xFF5C4300);
  static const bg = Color(0xFFF5F7FF);
  static const surface = Color(0xFFFFFFFF);
  static const ink = Color(0xFF2B3352);
  static const muted = Color(0xFF6B7494);
  static const line = Color(0xFFE2E7F7);
  static const shadow = Color(0x1F4A5BB0);
  static const soft = Color(0xFFEDF1FF);
  static const good = Color(0xFF23895C);
  static const bad = Color(0xFFC4473D);

  static const body = 'Nunito';
  static const display = 'Baloo 2';

  static ThemeData theme(Brightness b) {
    final p = b == Brightness.dark ? Palette.dark : Palette.light;
    final base = ThemeData(
      useMaterial3: true,
      brightness: b,
      colorSchemeSeed: blue,
      scaffoldBackgroundColor: p.bg,
      fontFamily: body,
    );
    final text = base.textTheme.apply(bodyColor: p.ink, displayColor: p.ink, fontFamily: body);
    return base.copyWith(
      textTheme: text.copyWith(
        headlineLarge: text.headlineLarge?.copyWith(fontFamily: display, fontWeight: FontWeight.w800),
        headlineMedium: text.headlineMedium?.copyWith(fontFamily: display, fontWeight: FontWeight.w800),
        titleLarge: text.titleLarge?.copyWith(fontFamily: display, fontWeight: FontWeight.w700),
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: p.bg,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        foregroundColor: p.ink,
        titleTextStyle: TextStyle(fontFamily: display, fontSize: 22, fontWeight: FontWeight.w700, color: p.ink),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: p.soft,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide.none),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(color: p.border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: blue, width: 2),
        ),
      ),
      snackBarTheme: const SnackBarThemeData(behavior: SnackBarBehavior.floating),
      pageTransitionsTheme: PageTransitionsTheme(
        builders: {for (final t in TargetPlatform.values) t: FadeUpwardsPageTransitionsBuilder()},
      ),
    );
  }
}

class Palette {
  const Palette._(this.bg, this.surface, this.ink, this.border, this.shadow, this.soft, this.muted);
  final Color bg, surface, ink, border, shadow, soft, muted;

  static const light = Palette._(Brand.bg, Brand.surface, Brand.ink, Brand.line, Brand.shadow, Brand.soft, Brand.muted);
  static const dark = Palette._(
    Color(0xFF151A2E),
    Color(0xFF1F2640),
    Color(0xFFEEF1FF),
    Color(0xFF2F3858),
    Color(0x59000000),
    Color(0xFF262F52),
    Color(0xFFA6AFD0),
  );

  static Palette of(BuildContext c) => Theme.of(c).brightness == Brightness.dark ? dark : light;
}

/// Vrai quand l'élève a demandé moins d'animations (réglage du système) : tout devient instantané.
bool calmMotion(BuildContext context) => MediaQuery.maybeDisableAnimationsOf(context) ?? false;

/// Carte aux coins arrondis et ombre diffuse.
class ChunkCard extends StatelessWidget {
  const ChunkCard({super.key, required this.child, this.color, this.padding = const EdgeInsets.all(22)});
  final Widget child;
  final Color? color;
  final EdgeInsets padding;

  @override
  Widget build(BuildContext context) {
    final p = Palette.of(context);
    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: color ?? p.surface,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: p.border),
        boxShadow: [BoxShadow(color: p.shadow, blurRadius: 24, offset: const Offset(0, 8))],
      ),
      child: child,
    );
  }
}

/// Bouton arrondi qui se soulève au survol et s'enfonce doucement au clic (petit son discret).
class PressButton extends StatefulWidget {
  const PressButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.primary = false,
    this.color,
    this.textColor,
    this.big = false,
    this.icon,
  });
  final String label;
  final VoidCallback? onPressed;
  final bool primary, big;
  final Color? color, textColor;
  final IconData? icon;

  @override
  State<PressButton> createState() => _PressButtonState();
}

class _PressButtonState extends State<PressButton> {
  bool _down = false;
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final p = Palette.of(context);
    final enabled = widget.onPressed != null;
    final custom = widget.color;
    final fg = widget.textColor ?? (widget.primary ? Colors.white : p.ink);
    final scale = _down ? .96 : (_hover && enabled ? 1.02 : 1.0);
    return Opacity(
      opacity: enabled ? 1 : .5,
      child: MouseRegion(
        cursor: enabled ? SystemMouseCursors.click : SystemMouseCursors.basic,
        onEnter: (_) => setState(() => _hover = true),
        onExit: (_) => setState(() => _hover = false),
        child: GestureDetector(
          onTapDown: enabled ? (_) => setState(() => _down = true) : null,
          onTapCancel: () => setState(() => _down = false),
          onTapUp: enabled
              ? (_) {
                  setState(() => _down = false);
                  Sounds.tap();
                  widget.onPressed!();
                }
              : null,
          child: Semantics(
            button: true,
            enabled: enabled,
            label: widget.label,
            child: AnimatedScale(
              scale: scale,
              duration: calmMotion(context) ? Duration.zero : const Duration(milliseconds: 140),
              curve: Curves.easeOutBack,
              child: Container(
                padding: EdgeInsets.symmetric(horizontal: widget.big ? 28 : 20, vertical: widget.big ? 16 : 12),
                decoration: BoxDecoration(
                  color: custom ?? (widget.primary ? null : p.surface),
                  gradient: custom == null && widget.primary
                      ? const LinearGradient(colors: [Brand.blue, Brand.lilac])
                      : null,
                  borderRadius: BorderRadius.circular(16),
                  border: widget.primary || custom != null ? null : Border.all(color: p.border, width: 1.5),
                  boxShadow: enabled
                      ? [
                          BoxShadow(
                            color: widget.primary ? Brand.blue.withValues(alpha: .28) : p.shadow,
                            blurRadius: _down ? 6 : 16,
                            offset: Offset(0, _down ? 2 : 6),
                          ),
                        ]
                      : null,
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    if (widget.icon != null) ...[
                      Icon(widget.icon, size: widget.big ? 22 : 18, color: fg),
                      const SizedBox(width: 8),
                    ],
                    Flexible(
                      child: Text(
                        widget.label,
                        textAlign: TextAlign.center,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(color: fg, fontWeight: FontWeight.w800, fontSize: widget.big ? 18 : 15),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Petite étiquette colorée (type d'exercice, « Facultatif », etc.).
class Pill extends StatelessWidget {
  const Pill(this.text, {super.key, this.color = Brand.soft, this.textColor = Brand.ink, this.icon});
  final String text;
  final Color color, textColor;
  final IconData? icon;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
    decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(99)),
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        if (icon != null) ...[Icon(icon, size: 15, color: textColor), const SizedBox(width: 5)],
        Text(text, style: TextStyle(color: textColor, fontWeight: FontWeight.w800, fontSize: 13)),
      ],
    ),
  );
}

/// Tag DEMO.
class DemoTag extends StatelessWidget {
  const DemoTag({super.key});
  @override
  Widget build(BuildContext context) => const Pill('DEMO', color: Brand.sun, textColor: Brand.sunInk);
}

/// Apparition douce (fondu et légère montée), décalée par `delay`.
class Rise extends StatefulWidget {
  const Rise({super.key, required this.child, this.delay = Duration.zero});
  final Widget child;
  final Duration delay;

  @override
  State<Rise> createState() => _RiseState();
}

class _RiseState extends State<Rise> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 480));
  late final Animation<double> _t = CurvedAnimation(parent: _c, curve: Curves.easeOutCubic);

  @override
  void initState() {
    super.initState();
    Future.delayed(widget.delay, () {
      if (mounted) _c.forward();
    });
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (calmMotion(context)) return widget.child;
    return AnimatedBuilder(
      animation: _t,
      builder: (_, child) => Opacity(
        opacity: _t.value,
        child: Transform.translate(offset: Offset(0, 16 * (1 - _t.value)), child: child),
      ),
      child: widget.child,
    );
  }
}

/// Barre de progression animée.
class AnimBar extends StatelessWidget {
  const AnimBar({super.key, required this.value, this.height = 14});
  final double value;
  final double height;

  @override
  Widget build(BuildContext context) {
    final p = Palette.of(context);
    return Container(
      height: height,
      decoration: BoxDecoration(color: p.soft, borderRadius: BorderRadius.circular(99)),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(99),
        child: TweenAnimationBuilder<double>(
          tween: Tween(begin: 0, end: value.clamp(0, 1)),
          duration: calmMotion(context) ? Duration.zero : const Duration(milliseconds: 900),
          curve: Curves.easeOutCubic,
          builder: (_, v, _) => Align(
            alignment: Alignment.centerLeft,
            child: FractionallySizedBox(
              widthFactor: v,
              child: Container(
                decoration: const BoxDecoration(gradient: LinearGradient(colors: [Brand.mint, Brand.sky])),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Nombre qui monte jusqu'à sa valeur.
class CountUp extends StatelessWidget {
  const CountUp(this.value, {super.key, this.style, this.suffix = ''});
  final int value;
  final TextStyle? style;
  final String suffix;

  @override
  Widget build(BuildContext context) => TweenAnimationBuilder<int>(
    tween: IntTween(begin: 0, end: value),
    duration: calmMotion(context) ? Duration.zero : const Duration(milliseconds: 800),
    curve: Curves.easeOutCubic,
    builder: (_, v, _) => Text('$v$suffix', style: style),
  );
}

/// Cadre commun des pages : titre, largeur maximale, défilement, apparition douce des blocs.
class PageFrame extends StatelessWidget {
  const PageFrame({super.key, required this.title, required this.children, this.trailing});
  final String title;
  final Widget? trailing;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) => Center(
    child: ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 920),
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(fontFamily: Brand.display, fontSize: 32, fontWeight: FontWeight.w800, height: 1.15),
                ),
              ),
              ?trailing,
            ],
          ),
          const SizedBox(height: 18),
          for (var i = 0; i < children.length; i++)
            Padding(
              padding: const EdgeInsets.only(bottom: 18),
              child: Rise(delay: Duration(milliseconds: 50 * math.min(i, 8)), child: children[i]),
            ),
        ],
      ),
    ),
  );
}

/// Tuile de statistique avec icône, valeur animée et libellé.
class StatTile extends StatelessWidget {
  const StatTile({
    super.key,
    required this.icon,
    required this.color,
    required this.value,
    required this.label,
    this.suffix = '',
  });
  final IconData icon;
  final Color color;
  final int value;
  final String label, suffix;

  @override
  Widget build(BuildContext context) {
    final p = Palette.of(context);
    return SizedBox(
      width: 210,
      child: ChunkCard(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(color: color.withValues(alpha: .16), borderRadius: BorderRadius.circular(14)),
              child: Icon(icon, size: 26, color: color),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  CountUp(
                    value,
                    suffix: suffix,
                    style: const TextStyle(fontFamily: Brand.display, fontSize: 28, fontWeight: FontWeight.w800, height: 1),
                  ),
                  Text(label, style: TextStyle(color: p.muted, fontWeight: FontWeight.w600)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Anneau de progression animé (valeur sur total).
class RingProgress extends StatelessWidget {
  const RingProgress({super.key, required this.done, required this.total, this.size = 120});
  final int done, total;
  final double size;

  @override
  Widget build(BuildContext context) {
    final p = Palette.of(context);
    final ratio = total == 0 ? 0.0 : (done / total).clamp(0.0, 1.0);
    return SizedBox(
      width: size,
      height: size,
      child: Stack(
        alignment: Alignment.center,
        children: [
          SizedBox.expand(
            child: TweenAnimationBuilder<double>(
              tween: Tween(begin: 0, end: ratio),
              duration: calmMotion(context) ? Duration.zero : const Duration(milliseconds: 1200),
              curve: Curves.easeOutCubic,
              builder: (_, pct, _) => CircularProgressIndicator(
                value: pct,
                strokeWidth: 10,
                strokeCap: StrokeCap.round,
                backgroundColor: p.soft,
                color: Brand.mint,
              ),
            ),
          ),
          Text('$done/$total',
              style: const TextStyle(fontFamily: Brand.display, fontSize: 24, fontWeight: FontWeight.w800)),
        ],
      ),
    );
  }
}

/// Encadré de résultat (réussi ou à revoir), en couleurs douces.
class ResultBox extends StatelessWidget {
  const ResultBox({super.key, required this.ok, required this.child});
  final bool ok;
  final Widget child;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(
      color: (ok ? Brand.mint : Brand.coral).withValues(alpha: .14),
      borderRadius: BorderRadius.circular(16),
    ),
    child: child,
  );
}

void snack(BuildContext c, String msg) => ScaffoldMessenger.of(c)
  ..hideCurrentSnackBar()
  ..showSnackBar(
    SnackBar(
      content: Text(msg, style: const TextStyle(fontWeight: FontWeight.w800, color: Brand.sunInk)),
      backgroundColor: Brand.sun,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      duration: const Duration(seconds: 2),
    ),
  );

/// Petite fête après une bonne réponse : confettis pastel et texte qui s'envole (« +1 », « Bravo ! »).
/// Rien ne bouge si l'élève a demandé moins d'animations ; le son reste géré par [Sounds].
void celebrate(BuildContext context, {String label = 'Bravo !'}) {
  final overlay = Overlay.maybeOf(context);
  if (overlay == null || calmMotion(context)) return;
  late final OverlayEntry entry;
  entry = OverlayEntry(builder: (_) => _Celebration(label: label, onDone: () => entry.remove()));
  overlay.insert(entry);
}

class _Celebration extends StatefulWidget {
  const _Celebration({required this.label, required this.onDone});
  final String label;
  final VoidCallback onDone;

  @override
  State<_Celebration> createState() => _CelebrationState();
}

class _CelebrationState extends State<_Celebration> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1500))
    ..forward().whenComplete(widget.onDone);
  final _seed = math.Random();
  late final List<_Bit> _bits = List.generate(36, (_) {
    final angle = -math.pi / 2 + (_seed.nextDouble() - .5) * math.pi * 1.1;
    return _Bit(angle, 260 + _seed.nextDouble() * 220, _confetti[_seed.nextInt(_confetti.length)],
        5 + _seed.nextDouble() * 6, _seed.nextDouble() * math.pi);
  });

  static const _confetti = [Brand.blue, Brand.lilac, Brand.sun, Brand.coral, Brand.mint, Brand.sky];

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => IgnorePointer(
    child: AnimatedBuilder(
      animation: _c,
      builder: (context, _) {
        final t = _c.value;
        final rise = Curves.easeOutCubic.transform(math.min(1, t * 1.6));
        return Stack(
          children: [
            Positioned.fill(child: CustomPaint(painter: _ConfettiPainter(_bits, t))),
            Align(
              alignment: Alignment(0, .1 - .35 * rise),
              child: Opacity(
                opacity: t < .7 ? 1 : (1 - (t - .7) / .3),
                child: Transform.scale(
                  scale: .7 + .3 * Curves.elasticOut.transform(math.min(1, t * 2)),
                  child: Text(
                    widget.label,
                    style: const TextStyle(
                      fontFamily: Brand.display,
                      fontSize: 44,
                      fontWeight: FontWeight.w800,
                      color: Brand.blue,
                      decoration: TextDecoration.none,
                      shadows: [Shadow(color: Colors.white, blurRadius: 12)],
                    ),
                  ),
                ),
              ),
            ),
          ],
        );
      },
    ),
  );
}

class _Bit {
  _Bit(this.angle, this.speed, this.color, this.size, this.spin);
  final double angle, speed, size, spin;
  final Color color;
}

class _ConfettiPainter extends CustomPainter {
  _ConfettiPainter(this.bits, this.t);
  final List<_Bit> bits;
  final double t;

  @override
  void paint(Canvas canvas, Size size) {
    final origin = Offset(size.width / 2, size.height * .55);
    for (final bit in bits) {
      final d = bit.speed * t;
      final position = origin + Offset(math.cos(bit.angle) * d, math.sin(bit.angle) * d + 420 * t * t);
      final paint = Paint()..color = bit.color.withValues(alpha: (1 - t).clamp(0, 1));
      canvas.save();
      canvas.translate(position.dx, position.dy);
      canvas.rotate(bit.spin + t * 8);
      canvas.drawRRect(
        RRect.fromRectAndRadius(Rect.fromCenter(center: Offset.zero, width: bit.size, height: bit.size * .6),
            const Radius.circular(2)),
        paint,
      );
      canvas.restore();
    }
  }

  @override
  bool shouldRepaint(_ConfettiPainter old) => old.t != t;
}
