import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiClient {
  static Future<Map<String, dynamic>> sendTask(String text) async {
    final res = await http.post(
      Uri.parse("http://10.0.2.2:8000/task"),
      headers: {"Content-Type": "application/json"},
      body: jsonEncode({
        "user_id": "user_1",
        "text": text
      }),
    );

    return jsonDecode(res.body);
  }
}
