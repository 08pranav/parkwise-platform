import 'package:core/core.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:owner_app/features/auth/view/login_screen.dart';

AuthBloc buildBloc() {
  final tokens = TokenManager(SecureStorageService());
  return AuthBloc(
    authService: AuthService(Dio(), tokens),
    tokenManager: tokens,
  );
}

Future<AuthBloc> pumpLogin(WidgetTester tester) async {
  tester.view.physicalSize = const Size(900, 1600);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final bloc = buildBloc();
  addTearDown(bloc.close);
  await tester.pumpWidget(
    MaterialApp(
      home: BlocProvider<AuthBloc>.value(
        value: bloc,
        child: const LoginScreen(),
      ),
    ),
  );
  return bloc;
}

void main() {
  testWidgets('login screen renders an email and a password field', (
    tester,
  ) async {
    await pumpLogin(tester);
    expect(find.byType(TextFormField), findsAtLeastNWidgets(2));
  });

  testWidgets(
    'submitting an empty form shows validation errors and stays put',
    (tester) async {
      final bloc = await pumpLogin(tester);
      await tester.ensureVisible(find.byType(PrimaryButton).first);
      await tester.tap(find.byType(PrimaryButton).first);
      await tester.pump();
      expect(find.text('Email is required'), findsOneWidget);
      expect(find.text('Password is required'), findsOneWidget);
      expect(bloc.state, isNot(isA<Authenticated>()));
    },
  );

  testWidgets('an email without @ is rejected', (tester) async {
    await pumpLogin(tester);
    await tester.enterText(find.byType(TextFormField).first, 'not-an-email');
    await tester.ensureVisible(find.byType(PrimaryButton).first);
    await tester.tap(find.byType(PrimaryButton).first);
    await tester.pump();
    expect(find.text('Enter a valid email'), findsOneWidget);
  });
}
