import 'package:material_ui/material_ui.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:viethome_frontend/main.dart';

void main() {
  testWidgets('Smart Home dashboard renders', (WidgetTester tester) async {
    await tester.pumpWidget(const SmartHomeApp());

    expect(find.text('Smart Home'), findsOneWidget);
    expect(find.text('Thiết bị trong nhà'), findsOneWidget);
    expect(find.text('Điều khiển bằng câu lệnh'), findsOneWidget);
    expect(find.byKey(const ValueKey('text-command-input')), findsOneWidget);

    // Dispose the page so its periodic status timer is cancelled.
    await tester.pumpWidget(const SizedBox.shrink());
  });
}
