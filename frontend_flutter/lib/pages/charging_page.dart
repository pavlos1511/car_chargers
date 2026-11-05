import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'stations_page.dart'; // Βεβαιώσου ότι κάνεις import τη σελίδα του χάρτη

enum ChargingState { waiting, charging, finished }

class ChargingPage extends StatefulWidget {
  final String pointId;
  const ChargingPage({super.key, required this.pointId});

  @override
  State<ChargingPage> createState() => _ChargingPageState();
}

class _ChargingPageState extends State<ChargingPage> {
  ChargingState state = ChargingState.waiting;
  bool isLoading = false;
  
  // Μεταβλητές για τα στατιστικά της φόρτισης (Simulator)
  Timer? _timer;
  int _secondsElapsed = 0;
  double _kwh = 0.0;
  double _cost = 0.0;
  final double _pricePerKwh = 0.30; // Ενδεικτική τιμή

  final String baseUrl = "http://localhost:9876/api"; // Προσοχή στην IP (localhost ή 10.0.2.2)

  @override
  void initState() {
    super.initState();
    _checkInitialStatus();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  // Έλεγχος: Μήπως ο φορτιστής είναι ήδη σε κατάσταση charging;
  Future<void> _checkInitialStatus() async {
    try {
      final response = await http.get(Uri.parse("$baseUrl/point/${widget.pointId}"));
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        if (data['status'] == 'charging') {
          // Αν είναι ήδη charging, συνεχίζουμε από εκεί που είμασταν (περίπου)
          setState(() {
            state = ChargingState.charging;
            _startTimer();
          });
        }
      }
    } catch (e) {
      print("Error checking status: $e");
    }
  }

  // --- 1. Έναρξη Φόρτισης ---
  Future<void> startCharging() async {
    setState(() => isLoading = true);

    try {
      // ΒΗΜΑ Α: Ελέγχουμε την τρέχουσα κατάσταση στον Server
      final statusResponse = await http.get(Uri.parse("$baseUrl/point/${widget.pointId}"));
      
      if (statusResponse.statusCode != 200) throw Exception("Σφάλμα σύνδεσης");

      final pointData = json.decode(statusResponse.body);
      final currentStatus = pointData['status'];

      // ΛΟΓΙΚΗ ΓΙΑ ΤΟΝ "ΑΡΓΟΠΟΡΗΜΕΝΟ" ΧΡΗΣΤΗ
      if (currentStatus == 'available') {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text("⚠️ Η κράτησή σας έληξε, αλλά ο φορτιστής είναι ακόμα ελεύθερος. Η φόρτιση ξεκινά!"),
              backgroundColor: Colors.orange,
              duration: Duration(seconds: 4),
            ),
          );
        }
      } else if (currentStatus != 'reserved' && currentStatus != 'charging') {
        // Αν είναι offline ή malfunction ή reserved από άλλον (εδώ απλοποιούμε)
        _showError("Ο φορτιστής δεν είναι διαθέσιμος (Status: $currentStatus)");
        setState(() => isLoading = false);
        return;
      }

      // ΒΗΜΑ Β: Στέλνουμε εντολή να γίνει 'charging'
      final url = "$baseUrl/updpoint/${widget.pointId}";
      final body = json.encode({"status": "charging", "kwhprice": _pricePerKwh});

      final response = await http.post(
        Uri.parse(url),
        headers: {"Content-Type": "application/json"},
        body: body,
      );

      if (response.statusCode == 200) {
        // --- Αποθήκευση Active Session ---
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString('active_charging_id', widget.pointId);
        
        setState(() {
          state = ChargingState.charging;
          isLoading = false;
        });
        _startTimer();
      } else {
        _showError("Αποτυχία εκκίνησης φόρτισης");
      }
    } catch (e) {
      _showError("Σφάλμα συστήματος: $e");
    } finally {
      if (mounted) setState(() => isLoading = false);
    }
  }

  // --- 2. Τερματισμός Φόρτισης ---
  Future<void> stopCharging() async {
    setState(() => isLoading = true);
    _timer?.cancel();

    try {
      // ΒΗΜΑ Α: Ενημέρωση status σε 'available'
      final updUrl = "$baseUrl/updpoint/${widget.pointId}";
      await http.post(
        Uri.parse(updUrl),
        headers: {"Content-Type": "application/json"},
        body: json.encode({"status": "available"}),
      );

      // ΒΗΜΑ Β: Καταγραφή Session (Ιστορικό)
      final sessionUrl = "$baseUrl/newsession";
      final now = DateTime.now();
      final start = now.subtract(Duration(seconds: _secondsElapsed));
      
      // Βοηθητική συνάρτηση μορφοποίησης ημερομηνίας
      String formatTime(DateTime dt) => dt.toString().substring(0, 16); // "YYYY-MM-DD HH:MM"

      final sessionBody = json.encode({
        "pointid": widget.pointId,
        "starttime": formatTime(start),
        "endtime": formatTime(now),
        "startsoc": 20, // Dummy τιμή
        "endsoc": 80,   // Dummy τιμή
        "totalkwh": double.parse(_kwh.toStringAsFixed(2)),
        "kwhprice": _pricePerKwh,
        "Amount": double.parse(_cost.toStringAsFixed(2))
      });

      await http.post(
        Uri.parse(sessionUrl),
        headers: {"Content-Type": "application/json"},
        body: sessionBody,
      );

      // --- Καθαρισμός Active Session ---
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove('active_charging_id');

      setState(() {
        state = ChargingState.finished;
        isLoading = false;
      });

    } catch (e) {
      _showError("Σφάλμα κατά τον τερματισμό");
      setState(() => isLoading = false);
    }
  }

  // --- Simulator Timer ---
  void _startTimer() {
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      setState(() {
        _secondsElapsed++;
        _kwh += 0.1; // Προσομοίωση ταχύτητας φόρτισης
        _cost = _kwh * _pricePerKwh;
      });
    });
  }

  void _showError(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), backgroundColor: Colors.red),
    );
  }

  void _handleBackButton() {
    if (state == ChargingState.charging) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Η φόρτιση είναι ενεργή! Πατήστε 'Διακοπή' πρώτα.")),
      );
    } else {
      Navigator.pop(context);
    }
  }

  void _backToMap() {
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => StationsPage()), 
      (route) => false
    );
  }

  // --- UI Builders ---

  Widget buildWaitingState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.ev_station, size: 80, color: Colors.blue),
          const SizedBox(height: 20),
          Text("Σταθμός: ${widget.pointId}", style: const TextStyle(fontSize: 20)),
          const SizedBox(height: 10),
          const Text("Είστε έτοιμοι;", style: TextStyle(fontSize: 16, color: Colors.grey)),
          const SizedBox(height: 40),
          SizedBox(
            width: 200,
            height: 50,
            child: ElevatedButton(
              style: ElevatedButton.styleFrom(backgroundColor: Colors.green, foregroundColor: Colors.white),
              onPressed: isLoading ? null : startCharging,
              child: isLoading 
                  ? const CircularProgressIndicator(color: Colors.white)
                  : const Text("Έναρξη Φόρτισης", style: TextStyle(fontSize: 18)),
            ),
          ),
        ],
      ),
    );
  }

  Widget buildChargingState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const CircularProgressIndicator(),
          const SizedBox(height: 30),
          const Text("Φόρτιση σε εξέλιξη...", style: TextStyle(fontSize: 22, color: Colors.blue, fontWeight: FontWeight.bold)),
          const SizedBox(height: 40),
          
          // Info Cards
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              _infoCard("Χρόνος", "${_secondsElapsed}s"),
              _infoCard("Ενέργεια", "${_kwh.toStringAsFixed(1)} kWh"),
              _infoCard("Κόστος", "${_cost.toStringAsFixed(2)} €"),
            ],
          ),
          
          const SizedBox(height: 50),
          
          SizedBox(
            width: 200,
            height: 50,
            child: ElevatedButton.icon(
              icon: const Icon(Icons.stop),
              label: const Text("Διακοπή Φόρτισης"),
              style: ElevatedButton.styleFrom(backgroundColor: Colors.red, foregroundColor: Colors.white),
              onPressed: isLoading ? null : stopCharging,
            ),
          )
        ],
      ),
    );
  }

  Widget _infoCard(String title, String value) {
    return Card(
      elevation: 4,
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            Text(title, style: const TextStyle(color: Colors.grey)),
            const SizedBox(height: 5),
            Text(value, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          ],
        ),
      ),
    );
  }

  Widget buildFinishedState() {
    return Center(child: Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const Icon(Icons.check_circle, size: 80, color: Colors.green),
        const SizedBox(height: 20),
        const Text("Η φόρτιση ολοκληρώθηκε!", style: TextStyle(fontSize: 22)),
        const SizedBox(height: 10),
        Text("Τελικό Κόστος: ${_cost.toStringAsFixed(2)} €", style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        const SizedBox(height: 40),
        ElevatedButton.icon(
          icon: const Icon(Icons.map),
          label: const Text("Επιστροφή στον Χάρτη"),
          onPressed: _backToMap,
        )
      ],
    ));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("Διαχείριση Φόρτισης"), 
        leading: IconButton(icon: const Icon(Icons.arrow_back), onPressed: _handleBackButton),
        backgroundColor: Colors.green.shade100,
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: switch (state) {
          ChargingState.waiting => buildWaitingState(),
          ChargingState.charging => buildChargingState(),
          ChargingState.finished => buildFinishedState(),
        },
      ),
    );
  }
}