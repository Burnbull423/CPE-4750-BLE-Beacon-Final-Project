from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
import logging
import time
import json
from bluepy.btle import Scanner, DefaultDelegate

# Configuration
host = "{Your AWS host link here}"
certPath = "{Your Cert path here}"
clientId = "{Your AWS Thing name here}" #For this the clientId of SenseHat_S25 was used
TARGET_MAC = "{MAC address of BLE Beacon for testing}"

# Global variable to store shadow state
shadow_state = {}

# Topics
shadow_topic = f"$aws/things/{clientId}/shadow/get"  # Use clientId as thing name

# Initialize AWSIoTMQTTClient
myAWSIoTMQTTClient = AWSIoTMQTTClient(clientId)
myAWSIoTMQTTClient.configureEndpoint(host, 8883)
myAWSIoTMQTTClient.configureCredentials(
    "{}RootCA1.pem".format(certPath),
    "{}SenseHat_S25-private.pem.key".format(certPath),
    "{}SenseHat_S25-cert.pem.crt".format(certPath)
)

# AWSIoTMQTTClient connection configuration
myAWSIoTMQTTClient.configureAutoReconnectBackoffTime(1, 32, 20)
myAWSIoTMQTTClient.configureOfflinePublishQueueing(-1)  # Infinite offline Publish queueing
myAWSIoTMQTTClient.configureDrainingFrequency(2)  # Draining: 2 Hz
myAWSIoTMQTTClient.configureConnectDisconnectTimeout(10)  # 10 sec
myAWSIoTMQTTClient.configureMQTTOperationTimeout(5)  # 5 sec

# Connect to AWS IoT Core
myAWSIoTMQTTClient.connect()

# Callback to handle the shadow get response
def shadow_get_callback(client, userdata, message):
    global shadow_state  # Ensure shadow_state is treated as a global variable
    try:
        payload = json.loads(message.payload)
        if "state" in payload:
            shadow_state = payload["state"]  # Store the state in the global variable
            print("Shadow State received:")
            print(json.dumps(shadow_state, indent=4))
        else:
            print("No state in the shadow response.")
    except Exception as e:
        print(f"Error parsing shadow response: {e}")

# Subscribe to the shadow response topic (this is the response to the publish below)
myAWSIoTMQTTClient.subscribe(f"$aws/things/{clientId}/shadow/get/accepted", 1, shadow_get_callback)

# Publishing a blank payload to the shadow will reply with the data currently in the shadow
myAWSIoTMQTTClient.publish(shadow_topic, "{}", 1)

# Wait for the shadow response to be processed
time.sleep(5)  # Adjust this time as needed to give enough time for the response


# Disconnect after receiving the shadow state
myAWSIoTMQTTClient.disconnect()

class ScanDelegate(DefaultDelegate):
    def __init__(self):
        DefaultDelegate.__init__(self)

def scan_for_target_mac():
    scanner = Scanner().withDelegate(ScanDelegate())
    print("🔍 Scanning for BLE beacon...")
    devices = scanner.scan(5.0)

    for dev in devices:
        if dev.addr.lower() == TARGET_MAC.lower():
            print(f"🎯 Found test beacon: {dev.addr}")
            return dev.addr.lower()
    print("❌ Test beacon not found.")
    return None

# Scan for the known test beacon
found_mac = scan_for_target_mac()

# Compare with MAC from shadow (if found)
try:
    shadow_mac = shadow_state["reported"]["MAC"].lower()
    print(f"📦 Shadow MAC: {shadow_mac}")
    
    if found_mac:
        if found_mac == shadow_mac:
            print("$ Payment allowed, MAC addresses match!")
        else:
            print(f"❌ Payment Denied. MAC addresses do not match.")
            print(f"Beacon: {found_mac}, Shadow: {shadow_mac}. ")
except KeyError:
    print("❌ 'macAddress' not found in device shadow.")

