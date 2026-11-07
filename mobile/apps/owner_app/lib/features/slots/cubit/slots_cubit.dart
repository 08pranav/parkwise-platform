import 'package:core/core.dart';
import 'package:dio/dio.dart';
import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../data/slots_repository.dart';

sealed class SlotsState extends Equatable {
  const SlotsState();
  @override
  List<Object?> get props => [];
}

class SlotsLoading extends SlotsState {
  const SlotsLoading();
}

class SlotsLoaded extends SlotsState {
  const SlotsLoaded(this.slots);
  final List<SlotModel> slots;
  @override
  List<Object?> get props => [slots];
}

class SlotsFailure extends SlotsState {
  const SlotsFailure(this.message);
  final String message;
  @override
  List<Object?> get props => [message];
}

class SlotsCubit extends Cubit<SlotsState> {
  SlotsCubit(this._repository, {required this.user})
      : super(const SlotsLoading());

  final SlotsRepository _repository;
  final UserModel user;

  Future<void> load() async {
    final societyId = user.society;
    if (societyId == null) {
      emit(const SlotsFailure('Your account is not linked to a society yet.'));
      return;
    }
    emit(const SlotsLoading());
    try {
      emit(SlotsLoaded(
        await _repository.mySlots(societyId: societyId, ownerId: user.id),
      ));
    } catch (e) {
      emit(SlotsFailure(_message(e)));
    }
  }

  /// Returns an error message, or null on success.
  Future<String?> setActive(SlotModel slot, bool isActive) async {
    try {
      await _repository.setActive(
        societyId: slot.society,
        slotId: slot.id,
        isActive: isActive,
      );
      await load();
      return null;
    } catch (e) {
      return _message(e);
    }
  }

  String _message(Object e) {
    final inner = e is DioException ? e.error : e;
    return inner is ApiException ? inner.message : 'Something went wrong. Please try again.';
  }
}
