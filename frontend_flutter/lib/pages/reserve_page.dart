import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'charging_page.dart';

class ReservePage extends StatefulWidget {
  final String pointId;

  const ReservePage({super.key, required this.pointId});

  @override
  State<ReservePage> createState() => _ReservePageState();
}

class _ReservePageState extends State<ReservePage> {
  // Προεπιλογή "30", αλλά ο χρήστης μπορεί να το αλλάξει ή να το σβήσει
  final TextEditingController _minutesController = TextEditingController(text: "30");
  
  // Προσοχή στο URL (localhost vs 10.0.2.2 για Android Emulator)
  final String baseUrl = "http://localhost:9876/api";

  bool isLoading = false;
  bool reservationSuccessful = false;
  String resultMessage = '';
  String? simulatedPin;

  Future<void> reservePoint() async {
    setState(() {
      isLoading = true;
      resultMessage = '';
      reservationSuccessful = false;
      simulatedPin = null;
    });

    String url;
    String inputText = _minutesController.text.trim();

    // ΛΟΓΙΚΗ API SPECIFICATION:
    // 1. Αν το πεδίο είναι κενό -> Καλούμε /reserve/:id
    //    Το backend θα βάλει αυτόματα 30'.
    if (inputText.isEmpty) {
      url = "$baseUrl/reserve/${widget.pointId}";
    } else {
      // 2. Αν υπάρχει αριθμός -> Καλούμε /reserve/:id/:minutes
      //    Δεν ελέγχουμε αν είναι > 30 ή > 60. Αφήνουμε το Backend να κάνει truncate.
      final int? minutes = int.tryParse(inputText);

      if (minutes == null || minutes <= 0) {
        setState(() {
          isLoading = false;
          resultMessage = "❌ Η διάρκεια κράτησης πρέπει να είναι έγκυρος αριθμός.";
        });
        return;
      }
      
      url = "$baseUrl/reserve/${widget.pointId}/$minutes";
    }

    try {
      final response = await http.post(Uri.parse(url));

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        
        // Simulating a PIN generation (logic from previous version)
        simulatedPin = (1000 + DateTime.now().millisecondsSinceEpoch % 9000).toString();

        // Αποθήκευση του Active Session
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString('active_charging_id', widget.pointId);

        setState(() {
          reservationSuccessful = true;
          // Εδώ εμφανίζουμε τον χρόνο λήξης που επέστρεψε το Backend.
          // Αν ζητήσαμε 90' και το backend έδωσε 60', εδώ θα φανεί η σωστή ώρα λήξης.
          resultMessage =
              "✅ Η δέσμευση ολοκληρώθηκε!\n"
              "Λήξη: ${data['reservationendtime']}\n"
              "PIN: $simulatedPin";
        });
      } else {
        setState(() {
          resultMessage = "❌ Αποτυχία δέσμευσης (${response.statusCode})";
        });
      }
    } catch (e) {
      setState(() {
        resultMessage = "❌ Σφάλμα σύνδεσης";
      });
    } finally {
      setState(() {
        isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Δέσμευση Φορτιστή")),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            Text("Φορτιστής ID: ${widget.pointId}", style: const TextStyle(fontSize: 18)),
            const SizedBox(height: 20),
            
            if (!reservationSuccessful) ...[
              TextField(
                controller: _minutesController,
                keyboardType: TextInputType.number,
                // Ενημερωμένο Label βάσει των οδηγιών
                decoration: const InputDecoration(
                  labelText: "Λεπτά (Κενό για 30', Max 60')", 
                  hintText: "π.χ. 45",
                  border: OutlineInputBorder()
                ),
              ),
              const SizedBox(height: 20),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: isLoading ? null : reservePoint,
                  child: isLoading ? const CircularProgressIndicator() : const Text("Δέσμευση"),
                ),
              ),
            ],

            if (resultMessage.isNotEmpty) ...[
              const SizedBox(height: 20),
              Text(
                resultMessage, 
                style: const TextStyle(fontSize: 16), 
                textAlign: TextAlign.center
              ),
            ],

            if (reservationSuccessful)
              Padding(
                padding: const EdgeInsets.only(top: 20.0),
                child: SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.green, 
                      foregroundColor: Colors.white
                    ),
                    icon: const Icon(Icons.bolt),
                    label: const Text("Μετάβαση στη Φόρτιση"),
                    onPressed: () {
                      Navigator.pushReplacement(
                        context,
                        MaterialPageRoute(builder: (_) => ChargingPage(pointId: widget.pointId)),
                      );
                    },
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}