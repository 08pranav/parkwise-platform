import 'package:core/core.dart';

/// Talks to the slot endpoints on behalf of a resident who owns slots.
class SlotsRepository {
  SlotsRepository(this._api);

  final ApiClient _api;

  Future<List<SlotModel>> mySlots({
    required String societyId,
    required String ownerId,
  }) async {
    final response = await _api.get<dynamic>(
      ApiEndpoints.societySlots(societyId),
      queryParameters: {'owner_id': ownerId},
    );
    final data = response.data;
    final items = data is Map<String, dynamic> && data['results'] is List
        ? data['results'] as List
        : data as List;
    return items
        .map((e) => SlotModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<void> create({
    required String societyId,
    required String slotNumber,
    required String floor,
    required String slotType,
    required String hourlyRate,
    required String availableFrom,
    required String availableTo,
  }) async {
    await _api.post<dynamic>(
      ApiEndpoints.societySlots(societyId),
      data: {
        'slot_number': slotNumber,
        'floor': floor,
        'slot_type': slotType,
        'hourly_rate': hourlyRate,
        'available_from_write': availableFrom,
        'available_to_write': availableTo,
      },
    );
  }

  Future<void> setActive({
    required String societyId,
    required String slotId,
    required bool isActive,
  }) async {
    await _api.post<dynamic>(
      ApiEndpoints.slotToggleActive(societyId, slotId),
      data: {'is_active': isActive},
    );
  }
}
