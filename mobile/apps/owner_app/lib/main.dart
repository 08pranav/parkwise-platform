import 'package:core/core.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';

import 'router.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await setupCoreDependencies(GetIt.I);
  await GetIt.I<TokenManager>().clearTokens();
  runApp(OwnerApp(themeNotifier: GetIt.I<ThemeNotifier>()));
}

class OwnerApp extends StatefulWidget {
  const OwnerApp({super.key, required this.themeNotifier});

  final ThemeNotifier themeNotifier;

  @override
  State<OwnerApp> createState() => _OwnerAppState();
}

class _OwnerAppState extends State<OwnerApp> {
  late final GoRouter _router = createRouter();

  @override
  Widget build(BuildContext context) {
    return BlocProvider.value(
      value: GetIt.I<AuthBloc>(),
      child: ListenableBuilder(
        listenable: widget.themeNotifier,
        builder: (context, _) => MaterialApp.router(
          title: 'ParkWise Owner',
          theme: AppTheme.lightTheme,
          darkTheme: AppTheme.darkTheme,
          themeMode: widget.themeNotifier.themeMode,
          routerConfig: _router,
          debugShowCheckedModeBanner: false,
        ),
      ),
    );
  }
}
