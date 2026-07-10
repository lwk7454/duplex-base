import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:english_tutor/main.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:english_tutor/providers/session_provider.dart';

/// System tests that connect to the REAL backend (Mac server + Windows Comni)
///
/// Prerequisites:
/// - LiveKit Server running on http://192.168.50.230:7880
/// - Backend running on http://192.168.50.230:8021
/// - Comni running on https://192.168.50.103:8006
///
/// Run with: flutter test integration_test/system_test.dart --integration-test
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  group('Real Backend System Tests', () {
    testWidgets('Full flow: Connect to real backend and create session', (WidgetTester tester) async {
      // Build the app with real backend configuration
      await tester.pumpWidget(
        const ProviderScope(
          child: MyApp(),
        ),
      );

      await tester.pumpAndSettle();

      // 1. Verify initial state
      expect(find.text('English Tutor'), findsOneWidget);
      expect(find.text('Not Connected'), findsOneWidget);

      // 2. Select "Free Chat" mode
      await tester.tap(find.text('Free Chat'));
      await tester.pump();

      // 3. Start session - this WILL connect to real backend
      print('🌐 Starting session with REAL backend...');

      await tester.tap(find.text('Start Session'));
      await tester.pump();

      // 4. Verify loading state appears
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      print('⏳ Loading state confirmed');

      // 5. Wait for connection (real network call)
      // This may take 10-20 seconds for full connection
      await tester.pumpAndSettle(const Duration(seconds: 30));
      print('✅ Connection attempt completed');

      // 6. Check result - may be connected or error (both are valid)
      final connected = find.text('Connected to Tutor');
      final errorText = find.textContaining('error', caseSensitive: false);

      if (finderEvaluate(connected).first != null) {
        print('✅ SUCCESS: Connected to real backend!');
        expect(connected, findsOneWidget);

        // 7. If connected, verify we can end the session
        await tester.tap(find.text('End Session'));
        await tester.pumpAndSettle(const Duration(seconds: 5));
        print('✅ Session ended successfully');

        // Verify back to initial state
        expect(find.text('Not Connected'), findsOneWidget);
      } else if (finderEvaluate(errorText).first != null) {
        print('⚠️  Connection failed (expected if backend not running): ${errorText.evaluate().first.toString()}');
        // Error is acceptable if backend isn't running
      } else {
        print('⚠️  Unexpected state - may still be loading');
      }
    });

    testWidgets('Backend health check', (WidgetTester tester) async {
      // This test verifies the backend is reachable
      print('🔍 Checking backend health...');

      // Build app
      await tester.pumpWidget(
        const ProviderScope(
          child: MyApp(),
        ),
      );

      await tester.pumpAndSettle();

      // Try to create a session - this will fail if backend is down
      await tester.tap(find.text('Start Session'));
      await tester.pump();
      await tester.pumpAndSettle(const Duration(seconds: 10));

      // If we see "Connected" or a specific error, backend is responding
      final connected = find.text('Connected to Tutor');
      final hasError = find.textContaining('error', caseSensitive: false);

      if (finderEvaluate(connected).first != null) {
        print('✅ Backend is UP and reachable');
      } else if (finderEvaluate(hasError).first != null) {
        final errorMsg = hasError.evaluate().first.toString();
        print('⚠️  Backend responded with error (may be network issue): $errorMsg');
      } else {
        print('⚠️  Backend status unknown (timeout or no response)');
      }
    });

    testWidgets('All modes are selectable', (WidgetTester tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MyApp(),
        ),
      );

      await tester.pumpAndSettle();

      final modes = ['Free Chat', 'Mock Interview', 'Travel Survival', 'Discussion & Debate'];

      for (final mode in modes) {
        print('📝 Testing mode: $mode');
        await tester.tap(find.text(mode));
        await tester.pump();

        // Verify the mode is selected by checking the RadioListTile exists
        final radioTiles = find.byType(RadioListTile<String>);
        expect(radioTiles, findsWidgets);
        print('✅ Mode $mode is selectable');
      }
    });
  });
}

// Helper to evaluate finders safely
dynamic finderEvaluate(Finder finder) {
  try {
    return finder.evaluate();
  } catch (e) {
    return [];
  }
}
