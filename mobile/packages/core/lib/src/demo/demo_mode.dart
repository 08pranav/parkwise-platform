import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../auth/bloc/auth_bloc.dart';
import '../auth/bloc/auth_event.dart';
import '../auth/bloc/auth_state.dart';
import '../config/env_config.dart';

/// Credentials of the seeded demo accounts (`manage.py seed_demo`).
/// They only exist on the public demo deployment and are intentionally public.
class DemoAccount {
  const DemoAccount(this.roleLabel, this.email);

  final String roleLabel;
  final String email;

  static const password = 'Demo@12345';

  static const resident = DemoAccount('Resident', 'user@parkwise.demo');
  static const owner = DemoAccount('Slot owner', 'owner@parkwise.demo');
  static const societyAdmin = DemoAccount(
    'Society admin',
    'admin@parkwise.demo',
  );
  static const guard = DemoAccount('Guard', 'guard@parkwise.demo');
  static const superAdmin = DemoAccount('Super admin', 'super@parkwise.demo');
}

/// Wraps an app with the public-demo banner when built with `--dart-define=DEMO_MODE=true`.
/// Use as `MaterialApp.router(builder: (context, child) => DemoModeWrapper(account: ..., child: child!))`.
class DemoModeWrapper extends StatelessWidget {
  const DemoModeWrapper({
    super.key,
    required this.child,
    required this.account,
    this.hint,
  });

  final Widget child;
  final DemoAccount account;

  /// Extra line shown under the banner text, e.g. test-payment details.
  final String? hint;

  @override
  Widget build(BuildContext context) {
    if (!EnvConfig.demoMode) return child;
    final scheme = Theme.of(context).colorScheme;
    return Column(
      children: [
        Material(
          color: scheme.tertiaryContainer,
          child: SafeArea(
            bottom: false,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              child: Row(
                children: [
                  Icon(
                    Icons.science_outlined,
                    size: 16,
                    color: scheme.onTertiaryContainer,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      hint == null
                          ? 'Public demo — data resets nightly'
                          : 'Public demo — data resets nightly · $hint',
                      style: TextStyle(
                        fontSize: 12,
                        color: scheme.onTertiaryContainer,
                      ),
                    ),
                  ),
                  _TryAsButton(account: account),
                ],
              ),
            ),
          ),
        ),
        Expanded(child: child),
      ],
    );
  }
}

class _TryAsButton extends StatelessWidget {
  const _TryAsButton({required this.account});

  final DemoAccount account;

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<AuthBloc, AuthState>(
      builder: (context, state) {
        if (state is Authenticated) return const SizedBox.shrink();
        return TextButton(
          style: TextButton.styleFrom(
            visualDensity: VisualDensity.compact,
            padding: const EdgeInsets.symmetric(horizontal: 10),
          ),
          onPressed: state is AuthLoading
              ? null
              : () => context.read<AuthBloc>().add(
                  AuthLoginRequested(
                    email: account.email,
                    password: DemoAccount.password,
                  ),
                ),
          child: Text('Try as ${account.roleLabel}'),
        );
      },
    );
  }
}
