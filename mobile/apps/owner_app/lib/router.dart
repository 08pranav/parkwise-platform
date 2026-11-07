import 'package:core/core.dart';
import 'package:flutter/material.dart';
import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';

import 'features/auth/view/login_screen.dart';
import 'features/auth/view/register_screen.dart';
import 'features/slots/view/my_slots_screen.dart';
import 'features/slots/view/slot_form_screen.dart';

/// Re-evaluates the router redirect whenever the auth state changes.
class _AuthRefresh extends ChangeNotifier {
  _AuthRefresh(AuthBloc bloc) {
    bloc.stream.listen((_) => notifyListeners());
  }
}

GoRouter createRouter() {
  final authBloc = GetIt.I<AuthBloc>();
  return GoRouter(
    initialLocation: '/slots',
    refreshListenable: _AuthRefresh(authBloc),
    redirect: (BuildContext context, GoRouterState state) {
      final authState = authBloc.state;
      final signedIn =
          authState is Authenticated && authState.user.role == 'user';
      final onPublicRoute =
          state.matchedLocation == '/login' ||
          state.matchedLocation == '/register';

      if (!signedIn && !onPublicRoute) return '/login';
      if (signedIn && onPublicRoute) return '/slots';
      return null;
    },
    routes: [
      GoRoute(path: '/login', builder: (_, _) => const LoginScreen()),
      GoRoute(path: '/register', builder: (_, _) => const RegisterScreen()),
      GoRoute(path: '/slots', builder: (_, _) => const MySlotsScreen()),
      GoRoute(path: '/slots/new', builder: (_, _) => const SlotFormScreen()),
      GoRoute(
        path: '/notifications',
        builder: (_, _) => NotificationInboxScreen(
          apiClient: GetIt.I<ApiClient>(),
          title: 'Notifications',
        ),
      ),
    ],
  );
}
