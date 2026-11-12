import 'package:core/core.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:get_it/get_it.dart';

import 'package:go_router/go_router.dart';

import 'router.dart';

final getIt = GetIt.instance;

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  await setupCoreDependencies(GetIt.I);
  final authBloc = GetIt.I<AuthBloc>();
  final themeNotifier = GetIt.I<ThemeNotifier>();
  authBloc.add(const AuthCheckRequested());

  runApp(ParkingApp(authBloc: authBloc, themeNotifier: themeNotifier));
}

class ParkingApp extends StatefulWidget {
  final AuthBloc authBloc;
  final ThemeNotifier themeNotifier;

  const ParkingApp({
    super.key,
    required this.authBloc,
    required this.themeNotifier,
  });

  @override
  State<ParkingApp> createState() => _ParkingAppState();
}

class _ParkingAppState extends State<ParkingApp> {
  late final GoRouter _router;

  @override
  void initState() {
    super.initState();
    _router = createRouter(widget.authBloc);
  }

  @override
  void dispose() {
    _router.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return BlocProvider.value(
      value: widget.authBloc,
      child: ListenableBuilder(
        listenable: widget.themeNotifier,
        builder: (context, _) => MaterialApp.router(
          title: 'ParkWise',
          debugShowCheckedModeBanner: false,
          builder: (context, child) => DemoModeWrapper(
            account: DemoAccount.resident,
            hint:
                'Stripe test card 4242 4242 4242 4242 · Razorpay test UPI success@razorpay',
            child: child!,
          ),
          theme: AppTheme.lightTheme,
          darkTheme: AppTheme.darkTheme,
          themeMode: widget.themeNotifier.themeMode,
          routerConfig: _router,
        ),
      ),
    );
  }
}
