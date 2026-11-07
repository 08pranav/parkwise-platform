import 'package:core/core.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:owner_app/features/slots/cubit/slots_cubit.dart';
import 'package:owner_app/features/slots/data/slots_repository.dart';

class FakeRepository extends SlotsRepository {
  FakeRepository() : super(ApiClient(Dio()));

  List<SlotModel> slots = [];
  Object? failure;
  final toggles = <String>[];

  @override
  Future<List<SlotModel>> mySlots({
    required String societyId,
    required String ownerId,
  }) async {
    if (failure != null) throw failure!;
    return slots;
  }

  @override
  Future<void> setActive({
    required String societyId,
    required String slotId,
    required bool isActive,
  }) async {
    if (failure != null) throw failure!;
    toggles.add('$slotId:$isActive');
  }
}

SlotModel slot(String id, {bool active = true}) => SlotModel(
  id: id,
  society: 'soc-1',
  slotNumber: id,
  slotType: 'car',
  state: 'available',
  ownershipType: 'resident',
  hourlyRate: '30.00',
  isActive: active,
  createdAt: '2026-06-01T10:00:00Z',
);

UserModel user({String? society = 'soc-1'}) => UserModel(
  id: 'user-1',
  email: 'a@example.com',
  phone: '9000000000',
  fullName: 'Asha',
  role: 'user',
  society: society,
);

void main() {
  late FakeRepository repo;

  setUp(() => repo = FakeRepository());

  test('starts loading, then emits the owner slots', () async {
    repo.slots = [slot('A-1'), slot('A-2')];
    final cubit = SlotsCubit(repo, user: user());
    expect(cubit.state, isA<SlotsLoading>());

    await cubit.load();

    final state = cubit.state as SlotsLoaded;
    expect(state.slots.map((s) => s.slotNumber), ['A-1', 'A-2']);
  });

  test('an empty list is a loaded state, not an error', () async {
    final cubit = SlotsCubit(repo, user: user());
    await cubit.load();
    expect((cubit.state as SlotsLoaded).slots, isEmpty);
  });

  test('a user without a society gets a clear failure', () async {
    final cubit = SlotsCubit(repo, user: user(society: null));
    await cubit.load();
    expect((cubit.state as SlotsFailure).message, contains('society'));
  });

  test(
    'network errors become a failure state with a friendly message',
    () async {
      repo.failure = DioException(requestOptions: RequestOptions(path: '/x'));
      final cubit = SlotsCubit(repo, user: user());
      await cubit.load();
      expect(cubit.state, isA<SlotsFailure>());
    },
  );

  test('API errors surface the server message', () async {
    repo.failure = DioException(
      requestOptions: RequestOptions(path: '/x'),
      error: const ApiException(message: 'Slot is not approved'),
    );
    final cubit = SlotsCubit(repo, user: user());
    await cubit.load();
    expect((cubit.state as SlotsFailure).message, 'Slot is not approved');
  });

  test('toggling reloads the list and reports success as null', () async {
    repo.slots = [slot('A-1')];
    final cubit = SlotsCubit(repo, user: user());
    final error = await cubit.setActive(slot('A-1'), false);
    expect(error, isNull);
    expect(repo.toggles, ['A-1:false']);
    expect(cubit.state, isA<SlotsLoaded>());
  });

  test('a failed toggle returns the error message', () async {
    repo.failure = DioException(
      requestOptions: RequestOptions(path: '/x'),
      error: const ApiException(message: 'Not your slot'),
    );
    final cubit = SlotsCubit(repo, user: user());
    expect(await cubit.setActive(slot('A-1'), true), 'Not your slot');
  });
}
