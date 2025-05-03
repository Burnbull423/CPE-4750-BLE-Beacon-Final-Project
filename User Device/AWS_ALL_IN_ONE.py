from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
import json
from bluepy.btle import Scanner, DefaultDelegate
import boto3

# === AWS Config ===
host = "{Your AWS host link here}"
certPath = "{Your Cert path here}"
clientId = "{Your AWS Thing name here}" #clientID for this is "SenseHat_S25"
topic_shadow_update = "$aws/things/SenseHat_S25/shadow/update"
AWS_REGION = "us-east-2"
DYNAMODB_TABLE = "Restaurant_Info" #See Restaruant_Info.csv in AWS DynamoDB folder

# === BLE Beacon Config ===
TARGET_MAC = "{MAC address of BLE beacon for testing}"

class ScanDelegate(DefaultDelegate):
    def __init__(self):
        super().__init__()

    def handleDiscovery(self, dev, isNewDev, isNewData):
        pass

def decode_manufacturer_data(data_hex):
    try:
        clean_hex = data_hex[4:]  # skip first 2 bytes (BLE Beacon manufacturer ID)
        bytes_data = bytes.fromhex(clean_hex)
        return bytes_data.decode('ascii')
    except Exception as e:
        print(f"❌ Failed to decode manufacturer data: {e}")
        return None

def get_restaurant_by_id(restaurant_id):
    try:
        dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
        table = dynamodb.Table(DYNAMODB_TABLE)
        response = table.get_item(Key={'restaurantID': str(restaurant_id)})
        if 'Item' in response:
            return response['Item']
        else:
            print(f"❓ No restaurant found for ID: {restaurant_id}")
            return None
    except Exception as e:
        print(f"❌ Error fetching from DynamoDB: {e}")
        return None

def get_menu_for_restaurant(restaurant_name):
    try:
        dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
        table = dynamodb.Table(restaurant_name)
        response = table.scan()
        return response.get('Items', [])
    except Exception as e:
        print(f"❌ Error fetching menu from table '{restaurant_name}': {e}")
        return []

def scan_for_beacon():
    scanner = Scanner().withDelegate(ScanDelegate())
    print("🔍 Scanning for BLE beacon...")
    devices = scanner.scan(5.0)

    for dev in devices:
        if dev.addr.lower() == TARGET_MAC:
            print(f"🎯 Found beacon: {dev.addr}")
            for (adtype, desc, value) in dev.getScanData():
                if desc == 'Manufacturer':
                    restaurant_id = decode_manufacturer_data(value)
                    if restaurant_id:
                        print(f"✅ Decoded Restaurant ID: {restaurant_id}")
                        restaurant_data = get_restaurant_by_id(restaurant_id)
                        return dev.addr.lower(), restaurant_data
    print("❌ Beacon not found or no valid manufacturer data.")
    return None, None

# === MQTT Setup ===
myAWSIoTMQTTClient = AWSIoTMQTTClient(clientId)
myAWSIoTMQTTClient.configureEndpoint(host, 8883)
myAWSIoTMQTTClient.configureCredentials(
    f"{certPath}RootCA1.pem",
    f"{certPath}SenseHat_S25-private.pem.key",
    f"{certPath}SenseHat_S25-cert.pem.crt"
)

myAWSIoTMQTTClient.configureAutoReconnectBackoffTime(1, 32, 20)
myAWSIoTMQTTClient.configureOfflinePublishQueueing(-1)
myAWSIoTMQTTClient.configureDrainingFrequency(2)
myAWSIoTMQTTClient.configureConnectDisconnectTimeout(10)
myAWSIoTMQTTClient.configureMQTTOperationTimeout(5)

print("🔌 Connecting to AWS IoT...")
myAWSIoTMQTTClient.connect()

# === Scan + Query + Publish ===
mac, restaurant_info = scan_for_beacon()

if mac:
    payload = {
        "state": {
            "reported": {
                "MAC": mac  # 🚀 MAC as 'temp' field
            }
        }
    }

    message_json = json.dumps(payload)
    myAWSIoTMQTTClient.publish(topic_shadow_update, message_json, 1)
    print(f"📤 Published MAC as 'MAC': {message_json}")

    if restaurant_info:
        print("\n🍽️ Restaurant Info:")
        for key, value in restaurant_info.items():
            print(f"  {key}: {value}")
else:
    print("⚠️ Beacon not found or failed to extract restaurant ID. Nothing published.")

# Get restaurant name and fetch menu
#restaurant_name = restaurant_info.get("Ohm_Cookin")
restaurant_name = "Ohm_Cookin"
if restaurant_name:
    print(f"\n📋 Fetching menu for: {restaurant_name}")
    menu_items = get_menu_for_restaurant(restaurant_name)
    menu_items.sort(key=lambda x: int(x.get("Order", 9999))) #boto3 gets items from the DynamoDB table in a slightly random order, so its sorted by the "Order" column before printing.
    if menu_items:
        print("\n📜 Menu Items:")
        for item in menu_items:
            if list(item.keys()) == ["dish"]:
                print(f"\n🔷 {item['dish'].upper()}")
            else:
                dish = item.get("dish", "")
                price = item.get("Price", "")
                description = item.get("Description", "")
                allergen = item.get("Allergen", "")

                print(f"\n🍽️ {dish} - {price}")
                print(f"  📃 {description}")
                if allergen and allergen.lower() != "none":
                    print(f"  ⚠️ Allergens: {allergen}")


    else:
        print("⚠️ No menu items found or table is empty.")
else:
    print("⚠️ Restaurant name not found in data.")

# === Clean Exit ===
myAWSIoTMQTTClient.disconnect()
print("✅ Done.")


