import 'package:material_ui/material_ui.dart';

/// Palette exacte du prototype HTML de référence.
class Brand {
  static const blue = Color(0xFF2F5BFF);
  static const sun = Color(0xFFFFC72C);
  static const coral = Color(0xFFFF5D5D);
  static const mint = Color(0xFF1FB67A);
  static const sunInk = Color(0xFF0E1B3D);
  static const bg = Color(0xFFEAF0FF);
  static const surface = Color(0xFFFFFFFF);
  static const ink = Color(0xFF0E1B3D);
  static const muted = Color(0xFF4A5780);
  static const line = Color(0xFF0E1B3D);
  static const shadow = Color(0xFF0E1B3D);
  static const soft = Color(0xFFDCE5FF);
  static const good = Color(0xFF0E7A50);
  static const bad = Color(0xFFB42323);

  static ThemeData theme(Brightness b) {
    final p = b == Brightness.dark ? Palette.dark : Palette.light;
    final base = ThemeData(
      useMaterial3: true,
      brightness: b,
      colorSchemeSeed: blue,
      scaffoldBackgroundColor: p.bg,
    );
    return base.copyWith(
      textTheme: base.textTheme.apply(bodyColor: p.ink, displayColor: p.ink),
    );
  }
}

class Palette {
  const Palette._(
    this.bg,
    this.surface,
    this.ink,
    this.border,
    this.shadow,
    this.soft,
    this.muted,
  );
  final Color bg, surface, ink, border, shadow, soft, muted;

  static const light = Palette._(
    Brand.bg,
    Brand.surface,
    Brand.ink,
    Brand.line,
    Brand.shadow,
    Brand.soft,
    Brand.muted,
  );
  static const dark = Palette._(
    Color(0xFF0B1330),
    Color(0xFF16225A),
    Color(0xFFF1F4FF),
    Color(0xFF4B5DB5),
    Color(0xFF050A1E),
    Color(0xFF1F2F7A),
    Color(0xFFA9B6E8),
  );

  static Palette of(BuildContext c) =>
      Theme.of(c).brightness == Brightness.dark ? dark : light;
}

/// Carte à bord épais et ombre pleine (style prototype).
class ChunkCard extends StatelessWidget {
  const ChunkCard({
    super.key,
    required this.child,
    this.color,
    this.padding = const EdgeInsets.all(22),
  });
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
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: p.border, width: 2),
        boxShadow: [BoxShadow(color: p.shadow, offset: const Offset(0, 6))],
      ),
      child: child,
    );
  }
}

/// Bouton en relief qui s'enfonce au clic.
class PressButton extends StatefulWidget {
  const PressButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.primary = false,
    this.color,
    this.textColor,
    this.big = false,
  });
  final String label;
  final VoidCallback? onPressed;
  final bool primary, big;
  final Color? color, textColor;

  @override
  State<PressButton> createState() => _PressButtonState();
}

class _PressButtonState extends State<PressButton> {
  bool _down = false;

  @override
  Widget build(BuildContext context) {
    final p = Palette.of(context);
    final enabled = widget.onPressed != null;
    final bg = widget.color ?? (widget.primary ? Brand.blue : p.surface);
    final fg = widget.textColor ?? (widget.primary ? Colors.white : p.ink);
    return Opacity(
      opacity: enabled ? 1 : .45,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(14),
          onTap: widget.onPressed,
          onHighlightChanged: (v) => setState(() => _down = v),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 80),
            transform: Matrix4.translationValues(0, _down ? 3 : 0, 0),
            padding: EdgeInsets.symmetric(
              horizontal: widget.big ? 30 : 22,
              vertical: widget.big ? 18 : 14,
            ),
            decoration: BoxDecoration(
              color: bg,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: p.border, width: 2),
              boxShadow: enabled
                  ? [
                      BoxShadow(
                        color: p.shadow,
                        offset: Offset(0, _down ? 1 : 4),
                      ),
                    ]
                  : null,
            ),
            child: Text(
              widget.label,
              textAlign: TextAlign.center,
              style: TextStyle(
                color: fg,
                fontWeight: FontWeight.w800,
                fontSize: widget.big ? 18 : 16,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Tag DEMO.
class DemoTag extends StatelessWidget {
  const DemoTag({super.key});
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
    decoration: BoxDecoration(
      color: Brand.sun,
      borderRadius: BorderRadius.circular(99),
      border: Border.all(color: Brand.sunInk, width: 2),
    ),
    child: const Text(
      'DEMO',
      style: TextStyle(
        color: Brand.sunInk,
        fontWeight: FontWeight.w800,
        fontSize: 12,
      ),
    ),
  );
}

/// Barre de progression animée.
class AnimBar extends StatelessWidget {
  const AnimBar({super.key, required this.value, this.height = 18});
  final double value;
  final double height;

  @override
  Widget build(BuildContext context) {
    final p = Palette.of(context);
    return Container(
      height: height,
      decoration: BoxDecoration(
        color: p.soft,
        borderRadius: BorderRadius.circular(99),
        border: Border.all(color: p.border, width: 2),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(99),
        child: TweenAnimationBuilder<double>(
          tween: Tween(begin: 0, end: value.clamp(0, 1)),
          duration: const Duration(milliseconds: 900),
          curve: Curves.easeOutCubic,
          builder: (_, v, __) => Align(
            alignment: Alignment.centerLeft,
            child: FractionallySizedBox(
              widthFactor: v,
              child: Container(
                decoration: const BoxDecoration(
                  gradient: LinearGradient(colors: [Brand.mint, Brand.sun]),
                ),
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
    duration: const Duration(milliseconds: 800),
    curve: Curves.easeOutCubic,
    builder: (_, v, __) => Text('$v$suffix', style: style),
  );
}

/// Cadre commun des pages : titre, largeur maximale, défilement.
class PageFrame extends StatelessWidget {
  const PageFrame({
    super.key,
    required this.title,
    required this.children,
    this.trailing,
  });
  final String title;
  final Widget? trailing;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) => Center(
    child: ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 920),
      child: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(
                    fontSize: 34,
                    fontWeight: FontWeight.w900,
                    height: 1.1,
                  ),
                ),
              ),
              if (trailing != null) trailing!,
            ],
          ),
          const SizedBox(height: 20),
          for (final c in children)
            Padding(padding: const EdgeInsets.only(bottom: 20), child: c),
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
      width: 260,
      child: ChunkCard(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Icon(icon, size: 38, color: color),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  CountUp(
                    value,
                    suffix: suffix,
                    style: const TextStyle(
                      fontSize: 30,
                      fontWeight: FontWeight.w900,
                      height: 1,
                    ),
                  ),
                  Text(label, style: TextStyle(color: p.muted)),
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
  const RingProgress({
    super.key,
    required this.done,
    required this.total,
    this.size = 130,
  });
  final int done, total;
  final double size;

  @override
  Widget build(BuildContext context) {
    final p = Palette.of(context);
    final C = 276.5;
    final offset = C * (1 - (done / total).clamp(0, 1));
    return SizedBox(
      width: size,
      height: size,
      child: TweenAnimationBuilder<double>(
        tween: Tween(begin: C, end: offset),
        duration: const Duration(milliseconds: 1200),
        curve: Curves.easeOutCubic,
        builder: (_, v, __) => Stack(
          alignment: Alignment.center,
          children: [
            SizedBox.expand(
              child: TweenAnimationBuilder<double>(
                tween: Tween(begin: 0, end: (done / total).clamp(0, 1)),
                duration: const Duration(milliseconds: 1200),
                curve: Curves.easeOutCubic,
                builder: (_, pct, __) => CircularProgressIndicator(
                  value: pct,
                  strokeWidth: 11,
                  strokeCap: StrokeCap.round,
                  backgroundColor: p.soft,
                  color: Brand.mint,
                ),
              ),
            ),
            Text(
              '$done/$total',
              style: const TextStyle(
                fontFamily: 'Baloo 2',
                fontSize: 26,
                fontWeight: FontWeight.w800,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Badge de validation (ok/ko).
class ResultBox extends StatelessWidget {
  const ResultBox({super.key, required this.ok, required this.child});
  final bool ok;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final p = Palette.of(context);
    final color = ok ? Brand.mint : Brand.coral;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: (ok ? Brand.good : Brand.bad).withValues(alpha: .15),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withValues(alpha: .5)),
      ),
      child: child,
    );
  }
}

void snack(BuildContext c, String msg) => ScaffoldMessenger.of(c)
  ..hideCurrentSnackBar()
  ..showSnackBar(
    SnackBar(
      content: Text(
        msg,
        style: const TextStyle(
          fontWeight: FontWeight.w800,
          color: Brand.sunInk,
        ),
      ),
      backgroundColor: Brand.sun,
      behavior: SnackBarBehavior.floating,
      duration: const Duration(seconds: 2),
    ),
  );
