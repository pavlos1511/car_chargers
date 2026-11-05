import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:url_launcher/url_launcher.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:geolocator/geolocator.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'reserve_page.dart';
import 'charging_page.dart';

class StationsPage extends StatefulWidget {
  const StationsPage({super.key});

  @override
  State<StationsPage> createState() => _StationsPageState();
}

class _StationsPageState extends State<StationsPage> with WidgetsBindingObserver {
  final String baseUrl = "http://localhost:9876/api";
  
  List<dynamic> stations = [];
  bool isLoading = false;
  String errorMessage = '';

  LatLng mapCenter = const LatLng(37.9838, 23.7275);
  final MapController _mapController = MapController();
  LatLng? userLocation;
  Timer? _debounce;
  String? activeChargingId;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    
    _requestLocation();     
    _checkActiveSession();  
    
    WidgetsBinding.instance.addPostFrameCallback((_) {
       _fetchStationsInView();
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _debounce?.cancel();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _refreshAll();
    }
  }

  // --- ΝΕΟ: Κεντρική συνάρτηση ανανέωσης ---
  // Καλείται κάθε φορά που γυρνάμε στον χάρτη
  Future<void> _refreshAll() async {
    // Μικρή καθυστέρηση για να προλάβει το backend να ενημερώσει τη βάση
    // (Λύνει το πρόβλημα που ανέφερες με τη γρήγορη αλλαγή κατάστασης)
    await Future.delayed(const Duration(milliseconds: 500));
    await _checkActiveSession();
    _fetchStationsInView();
  }

  // --- 1. Έλεγχος Active Session ---
  Future<void> _checkActiveSession() async {
    final prefs = await SharedPreferences.getInstance();
    final savedId = prefs.getString('active_charging_id');
    
    if (savedId != null) {
      try {
        final response = await http.get(Uri.parse("$baseUrl/point/$savedId"));
        if (response.statusCode == 200) {
          final data = json.decode(response.body);
          final status = data['status'];
          
          // Αν έγινε available/offline, καθαρίζουμε το banner
          if (status == 'available' || status == 'offline' || status == 'malfunction') {
            await prefs.remove('active_charging_id');
            if (mounted) setState(() => activeChargingId = null);
          } else {
            if (mounted) setState(() => activeChargingId = savedId);
          }
        }
      } catch (e) {
        // Αν αποτύχει η σύνδεση, κρατάμε το UI ως έχει
        if (mounted) setState(() => activeChargingId = savedId);
      }
    } else {
      if (mounted) setState(() => activeChargingId = null);
    }
    _fetchStationsInView();
  }

  // --- 2. Τοποθεσία (Βελτιωμένο) ---
  Future<void> _requestLocation() async {
    // Καθαρίζουμε τυχόν παλιά λάθη
    setState(() => errorMessage = '');

    bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      setState(() => errorMessage = 'Τα Services τοποθεσίας είναι κλειστά.');
      return;
    }

    LocationPermission permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied) {
        setState(() => errorMessage = 'Δεν δόθηκε άδεια τοποθεσίας.');
        return;
      }
    }
    if (permission == LocationPermission.deniedForever) {
      setState(() => errorMessage = 'Η τοποθεσία είναι μόνιμα αποκλεισμένη.');
      return;
    }

    // Πρώτα δοκιμάζουμε Last Known (γρήγορο)
    try {
      Position? lastKnown = await Geolocator.getLastKnownPosition();
      if (lastKnown != null) {
        _updateLocationUI(lastKnown);
      }
    } catch (_) {}

    // Τώρα ζητάμε φρέσκια (Αυξημένο timeout στα 20 δευτερόλεπτα)
    try {
      Position position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high, 
        timeLimit: const Duration(seconds: 20) 
      );
      _updateLocationUI(position);
    } catch (e) {
      print("Location error: $e");
      // Εμφάνιση μηνύματος αν αποτύχει (π.χ. timeout)
      if (userLocation == null) {
        setState(() => errorMessage = 'Αδυναμία εύρεσης τοποθεσίας (Timeout). Πατήστε το κουμπί κάτω δεξιά.');
      }
    }
  }

  void _updateLocationUI(Position position) {
    if (!mounted) return;
    setState(() {
      userLocation = LatLng(position.latitude, position.longitude);
      errorMessage = ''; // Καθαρισμός λαθών αν βρεθεί
    });
  }

  void _onRecenterPressed() {
    if (userLocation != null) {
      _mapController.move(userLocation!, 15.0);
      _fetchStationsInView();
    } else {
      // Ξαναδοκιμάζουμε αν πατήσει το κουμπί
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Προσπάθεια εύρεσης τοποθεσίας...")));
      _requestLocation().then((_) {
        if (userLocation != null) {
          _mapController.move(userLocation!, 15.0);
          _fetchStationsInView();
        }
      });
    }
  }

  // --- Fetching Logic ---
  void _fetchStationsInView() {
    try {
      final bounds = _mapController.camera.visibleBounds;
      if (bounds.northEast == bounds.southWest) return;

      fetchStations(
        neLat: bounds.northEast.latitude,
        neLon: bounds.northEast.longitude,
        swLat: bounds.southWest.latitude,
        swLon: bounds.southWest.longitude,
      );
    } catch (_) {}
  }

  Future<void> fetchStations({required double neLat, required double neLon, required double swLat, required double swLon}) async {
    final queryParams = {
      'ne_lat': neLat.toString(),
      'ne_lon': neLon.toString(),
      'sw_lat': swLat.toString(),
      'sw_lon': swLon.toString(),
    };

    try {
      final uri = Uri.parse("$baseUrl/points/bbox").replace(queryParameters: queryParams);
      final response = await http.get(uri);

      if (response.statusCode == 200) {
        if (!mounted) return;
        setState(() {
          stations = json.decode(response.body);
        });
      }
    } catch (e) {
      print("Error fetching stations: $e");
    }
  }

  // --- Markers ---
  Marker _buildUserMarker() {
    if (userLocation == null) return const Marker(point: LatLng(0,0), child: SizedBox());
    return Marker(
      point: userLocation!,
      width: 60, height: 60,
      child: Stack(
        alignment: Alignment.center,
        children: [
          Container(
            width: 60, height: 60,
            decoration: BoxDecoration(color: Colors.blue.withOpacity(0.3), shape: BoxShape.circle),
          ),
          Container(
            width: 20, height: 20,
            decoration: BoxDecoration(
              color: Colors.blue, 
              shape: BoxShape.circle, 
              border: Border.all(color: Colors.white, width: 3),
              boxShadow: const [BoxShadow(color: Colors.black26, blurRadius: 4)]
            ),
          ),
        ],
      ),
    );
  }

  List<Marker> _buildStationMarkers() {
    final List<Marker> markers = [];
    if (userLocation != null) markers.add(_buildUserMarker());

    for (var s in stations) {
      final lat = double.tryParse(s['lat'].toString()) ?? 0.0;
      final lon = double.tryParse(s['lon'].toString()) ?? 0.0;
      final id = s['pointid'] ?? s['point_id'];
      final provider = 'bestPowerGR'; 
      final status = s['status'] ?? 'unknown';
      final cost = s['kwhprice'] != null ? "${s['kwhprice']} €/kWh" : "-";

      Color pinColor = Colors.green; 
      if (status == 'charging') pinColor = Colors.blue;
      if (status == 'reserved') pinColor = Colors.orange;
      if (status == 'offline' || status == 'malfunction') pinColor = Colors.grey;

      markers.add(
        Marker(
          point: LatLng(lat, lon),
          width: 80, height: 80,
          child: GestureDetector(
            onTap: () => _showStationDetails(id.toString(), lat, lon, provider),
            child: Tooltip(
              // Add debug info to tooltip
              message: "$provider\nΚατάσταση: $status\nΤιμή: $cost",
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(color: Colors.black87, borderRadius: BorderRadius.circular(8)),
              textStyle: const TextStyle(color: Colors.white),
              child: Icon(Icons.location_on, color: pinColor, size: 45),
            ),
          ),
        ),
      );
    }
    return markers;
  }

  // --- Dialog & Navigation (ΔΙΟΡΘΩΜΕΝΟ) ---
  void _showStationDetails(String id, double lat, double lon, String provider) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('$provider (ID: $id)'),
        content: const Text('Τι θέλετε να κάνετε;'),
        actions: [
          TextButton.icon(
            icon: const Icon(Icons.directions),
            label: const Text('Πλοήγηση'),
            onPressed: () {
              Navigator.pop(ctx);
              _launchMaps(lat, lon);
            },
          ),
          ElevatedButton.icon(
            icon: const Icon(Icons.ev_station),
            label: const Text('Δέσμευση'),
            onPressed: () async {
              Navigator.pop(ctx);
              // ΕΔΩ ΕΙΝΑΙ Η ΛΥΣΗ: Περιμένουμε να γυρίσει
              await Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => ReservePage(pointId: id)),
              );
              // Και μετά καλούμε το refreshAll που έχει καθυστέρηση
              _refreshAll(); 
            },
          )
        ],
      ),
    );
  }

  Future<void> _launchMaps(double destLat, double destLon) async {
    Uri uri;
    if (userLocation != null) {
      uri = Uri.parse("https://www.google.com/maps/dir/?api=1&origin=${userLocation!.latitude},${userLocation!.longitude}&destination=$destLat,$destLon&travelmode=driving");
    } else {
      uri = Uri.parse("https://www.google.com/maps/search/?api=1&query=$destLat,$destLon");
    }
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Χάρτης Φορτιστών'),
        backgroundColor: Colors.green.shade100,
        actions: [
          IconButton(
             icon: const Icon(Icons.refresh),
             onPressed: _refreshAll, // Καλεί την πλήρη ανανέωση
             tooltip: 'Ανανέωση',
          )
        ],
      ),
      body: Stack(
        children: [
          FlutterMap(
            mapController: _mapController,
            options: MapOptions(
              initialCenter: mapCenter, 
              initialZoom: 14.0,
              onPositionChanged: (camera, hasGesture) {
                if (hasGesture) {
                  _debounce?.cancel();
                  _debounce = Timer(const Duration(milliseconds: 500), () => _fetchStationsInView());
                }
              },
              onMapReady: _fetchStationsInView,
            ),
            children: [
              TileLayer(
                urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                userAgentPackageName: 'com.evcharging.app',
              ),
              MarkerLayer(markers: _buildStationMarkers()),
            ],
          ),
          
          // BANNER (Με refresh στο tap)
          if (activeChargingId != null)
            Positioned(
              bottom: 80,
              left: 20,
              right: 20,
              child: Material(
                elevation: 8,
                borderRadius: BorderRadius.circular(16),
                color: Colors.blue.shade900.withOpacity(0.95),
                child: InkWell(
                  borderRadius: BorderRadius.circular(16),
                  onTap: () async {
                     await Navigator.push(
                       context,
                       MaterialPageRoute(builder: (_) => ChargingPage(pointId: activeChargingId!)),
                     );
                     _refreshAll(); // <--- Refresh και εδώ
                  },
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
                    child: Row(
                      children: [
                        const Icon(Icons.timelapse, color: Colors.white, size: 30),
                        const SizedBox(width: 16),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text(
                                "Ενεργή Δέσμευση / Φόρτιση",
                                style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16),
                              ),
                              const SizedBox(height: 4),
                              Text("Σταθμός ID: $activeChargingId", style: const TextStyle(color: Colors.white70)),
                            ],
                          ),
                        ),
                        const Icon(Icons.arrow_forward_ios, color: Colors.white70, size: 18),
                      ],
                    ),
                  ),
                ),
              ),
            ),
            
          // ERROR MESSAGE
          if (errorMessage.isNotEmpty)
             Positioned(
              top: 20, left: 20, right: 20,
              child: Card(
                color: Colors.red.shade100,
                child: Padding(padding: const EdgeInsets.all(8.0), child: Text(errorMessage, textAlign: TextAlign.center)),
              ),
             ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _onRecenterPressed,
        child: const Icon(Icons.my_location),
      ),
    );
  }
}