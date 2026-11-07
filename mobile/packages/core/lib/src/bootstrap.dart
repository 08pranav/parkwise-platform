import 'package:dio/dio.dart';
import 'package:get_it/get_it.dart';

import 'auth/auth_service.dart';
import 'auth/bloc/auth_bloc.dart';
import 'auth/token_manager.dart';
import 'config/app_constants.dart';
import 'config/env_config.dart';
import 'network/api_client.dart';
import 'network/dio_factory.dart';
import 'storage/secure_storage_service.dart';
import 'theme/theme_notifier.dart';

/// Registers the services every ParkWise app needs (storage, tokens, auth,
/// HTTP client, theme) in [getIt]. The API origin comes from
/// `--dart-define=API_BASE_URL` via [EnvConfig.current].
Future<void> setupCoreDependencies(GetIt getIt, {EnvConfig? config}) async {
  final env = config ?? EnvConfig.current;

  getIt.registerLazySingleton<SecureStorageService>(SecureStorageService.new);
  getIt.registerLazySingleton<TokenManager>(
    () => TokenManager(getIt<SecureStorageService>()),
  );

  final baseDio = Dio(
    BaseOptions(
      baseUrl: env.apiBaseUrl,
      connectTimeout: AppConstants.connectionTimeout,
      receiveTimeout: AppConstants.receiveTimeout,
      contentType: 'application/json',
    ),
  );

  getIt.registerLazySingleton<AuthService>(
    () => AuthService(baseDio, getIt<TokenManager>()),
  );
  getIt.registerLazySingleton<AuthBloc>(
    () => AuthBloc(
      authService: getIt<AuthService>(),
      tokenManager: getIt<TokenManager>(),
    ),
  );
  getIt.registerLazySingleton<Dio>(
    () => DioFactory.create(
      config: env,
      tokenManager: getIt<TokenManager>(),
      authBloc: getIt<AuthBloc>(),
    ),
  );
  getIt.registerLazySingleton<ApiClient>(() => ApiClient(getIt<Dio>()));
  getIt<AuthBloc>().setApiClient(getIt<ApiClient>());

  getIt.registerSingleton<ThemeNotifier>(await ThemeNotifier.create());
}
