import 'package:core/core.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';

import 'router.dart';

final getIt = GetIt.instance;

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await setupCoreDependencies(getIt);

  final themeNotifier = getIt<ThemeNotifier>();

  await getIt<TokenManager>().clearTokens();
  runApp(GuardApp(themeNotifier: themeNotifier));
}

class GuardApp extends StatefulWidget {
  final ThemeNotifier themeNotifier;
  const GuardApp({super.key, required this.themeNotifier});

  @override
  State<GuardApp> createState() => _GuardAppState();
}

class _GuardAppState extends State<GuardApp> {
  late final GoRouter _router;

  @override
  void initState() {
    super.initState();
    _router = createRouter();
  }

  @override
  Widget build(BuildContext context) {
    return BlocProvider.value(
      value: getIt<AuthBloc>(),
      child: ListenableBuilder(
        listenable: widget.themeNotifier,
        builder: (context, _) => MaterialApp.router(
          title: 'ParkWise Guard',
          theme: AppTheme.lightTheme,
          darkTheme: AppTheme.darkTheme,
          themeMode: widget.themeNotifier.themeMode,
          routerConfig: _router,
          debugShowCheckedModeBanner: false,
          builder: (context, child) =>
              DemoModeWrapper(account: DemoAccount.guard, child: child!),
        ),
      ),
    );
  }
}
