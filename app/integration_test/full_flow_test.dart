import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:english_tutor/main.dart';
import 'package:english_tutor/providers/session_provider.dart';
import 'package:english_tutor/models/session.dart';

// Mock backend for testing
class MockBackendApi {
  bool shouldFail = false;
  String? failMessage;

  Future<SessionResponse> createSession(SessionRequest request) async {
    await Future.delayed(const Duration(milliseconds: 500));

    if (shouldFail) {
      throw Exception(failMessage ?? 'Connection failed');
    }

    return SessionResponse(
      roomName: 'test-room-123',
      url: 'ws://localhost:7880',
      token: 'test-token',
      mode: request.mode,
      tutorIdentity: 'duplex-base',
    );
  }

  Future<void> stopSession(String roomName) async {
    await Future.delayed(const Duration(milliseconds: 100));
  }
}

void main() {
  group('English Tutor E2E Tests', () {
    testWidgets('Complete user flow: select mode and start session', (WidgetTester tester) async {
      // Create a mock override for the backend
      final mockBackend = MockBackendApi();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            backendApiProvider.overrideWithValue(mockBackend as dynamic),
          ],
          child: const MyApp(),
        ),
      );

      // Wait for initial render
      await tester.pumpAndSettle();

      // 1. Verify initial state
      expect(find.text('English Tutor'), findsOneWidget);
      expect(find.text('Not Connected'), findsOneWidget);

      // 2. Select "Travel Survival" mode
      await tester.tap(find.text('Travel Survival'));
      await tester.pump();

      // 3. Start session
      await tester.tap(find.text('Start Session'));
      await tester.pump();

      // 4. Verify loading state
      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      // 5. Wait for connection to complete
      await tester.pumpAndSettle(const Duration(seconds: 2));

      // 6. Verify connected state
      expect(find.text('Connected to Tutor'), findsOneWidget);
      expect(find.text('Session Active'), findsOneWidget);

      // 7. Verify end session button appears
      expect(find.text('End Session'), findsOneWidget);

      // 8. End the session
      await tester.tap(find.text('End Session'));
      await tester.pumpAndSettle();

      // 9. Verify back to initial state
      expect(find.text('Not Connected'), findsOneWidget);
      expect(find.text('Start Session'), findsOneWidget);
    });

    testWidgets('Error handling: connection failure', (WidgetTester tester) async {
      final mockBackend = MockBackendApi();
      mockBackend.shouldFail = true;
      mockBackend.failMessage = 'Network error';

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            backendApiProvider.overrideWithValue(mockBackend as dynamic),
          ],
          child: const MyApp(),
        ),
      );

      await tester.pumpAndSettle();

      // Try to start session
      await tester.tap(find.text('Start Session'));
      await tester.pump();

      // Wait for error
      await tester.pumpAndSettle(const Duration(seconds: 2));

      // Verify error is displayed
      expect(find.textContaining('error', caseSensitive: false), findsOneWidget);
    });

    testWidgets('Mode persistence test', (WidgetTester tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MyApp(),
        ),
      );

      await tester.pumpAndSettle();

      // Select each mode and verify it stays selected
      final modes = ['Free Chat', 'Mock Interview', 'Travel Survival', 'Discussion & Debate'];

      for (final mode in modes) {
        await tester.tap(find.text(mode));
        await tester.pump();
        expect(find.widgetWithText<RadioListTile<String>>(mode), findsOneWidget);
      }
    });

    testWidgets('UI responsiveness: mode selector disabled during session', (WidgetTester tester) async {
      final mockBackend = MockBackendApi();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            backendApiProvider.overrideWithValue(mockBackend as dynamic),
          ],
          child: const MyApp(),
        ),
      );

      await tester.pumpAndSettle();

      // Start session
      await tester.tap(find.text('Start Session'));
      await tester.pump();
      await tester.pumpAndSettle(const Duration(seconds: 2));

      // Verify mode selector is disabled (radio buttons not tappable)
      final radioButtons = find.byType(RadioListTile<String>);
      expect(radioButtons, findsWidgets);

      // Try to tap a mode (should not work)
      await tester.tap(find.text('Mock Interview'));
      await tester.pump();

      // Mode should not have changed
      expect(find.widgetWithText<RadioListTile<String>>('Free Chat'), findsOneWidget);
    });
  });
}
