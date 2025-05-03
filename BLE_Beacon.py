# ble_beacon.py
from pydbus import SystemBus
from gi.repository import GLib
import dbus
import dbus.exceptions
import dbus.mainloop.glib
import dbus.service

BLUEZ_SERVICE_NAME = 'org.bluez'
ADAPTER_IFACE = 'org.bluez.Adapter1'
ADVERTISING_MANAGER_IFACE = 'org.bluez.LEAdvertisingManager1'
ADVERTISEMENT_IFACE = 'org.bluez.LEAdvertisement1'
DBUS_OM_IFACE = 'org.freedesktop.DBus.ObjectManager'

class Advertisement(dbus.service.Object):
    PATH_BASE = '/org/bluez/example/advertisement'

    def __init__(self, bus, index):
        self.path = self.PATH_BASE + str(index)
        self.bus = bus
        self.ad_type = 'broadcast'
        self.service_uuids = []
        self.manufacturer_data = {
            0xFFFF: dbus.Array([0xDE, 0xAD, 0xBE, 0xEF, 0x00, 0x01], signature='y')
        }
        self.local_name = 'PiBeacon'
        self.include_tx_power = False

        dbus.service.Object.__init__(self, bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    @dbus.service.method(dbus_interface='org.freedesktop.DBus.Properties',
                         in_signature='ss', out_signature='v')
    def Get(self, interface, prop):
        if interface != ADVERTISEMENT_IFACE:
            raise dbus.exceptions.DBusException(
                'org.freedesktop.DBus.Error.InvalidArgs: Invalid interface')

        props = self.get_properties()[ADVERTISEMENT_IFACE]
        if prop not in props:
            raise dbus.exceptions.DBusException(
                'org.freedesktop.DBus.Error.InvalidArgs: Invalid property')
        return props[prop]

    @dbus.service.method(dbus_interface='org.freedesktop.DBus.Properties',
                         in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface):
        if interface != ADVERTISEMENT_IFACE:
            raise dbus.exceptions.DBusException(
                'org.freedesktop.DBus.Error.InvalidArgs: Invalid interface')

        return self.get_properties()[ADVERTISEMENT_IFACE]

    @dbus.service.method(dbus_interface=ADVERTISEMENT_IFACE,
                         in_signature='', out_signature='')
    def Release(self):
        print('Advertisement released')

    def get_properties(self):
        return {
            ADVERTISEMENT_IFACE: {
                'Type': self.ad_type,
                'ManufacturerData': dbus.Dictionary({
                0xFFFF: dbus.Array([
        0x54, 0x65, 0x6D, 0x70,  # Temp
        0x52, 0x65, 0x73, 0x74,  # Rest
        0x61, 0x75, 0x72, 0x61, 0x6E, 0x74  # aurant
    ], signature='y')
            }, signature='qv'),
                'LocalName': 'Restaurant',
                'IncludeTxPower': dbus.Boolean(False),
            }
        }


def find_adapter(bus):
    remote_om = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, '/'),
                               DBUS_OM_IFACE)
    objects = remote_om.GetManagedObjects()
    for path, interfaces in objects.items():
        if ADVERTISING_MANAGER_IFACE in interfaces:
            return path
    return None

def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    adapter_path = find_adapter(bus)
    if not adapter_path:
        print('Bluetooth adapter interface not found')
        return

    adapter_props = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, adapter_path),
                                   'org.freedesktop.DBus.Properties')
    adapter_props.Set(ADAPTER_IFACE, 'Powered', dbus.Boolean(1))

    ad_manager = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, adapter_path),
                                ADVERTISING_MANAGER_IFACE)

    advertisement = Advertisement(bus, 0)

    ad_manager.RegisterAdvertisement(advertisement.get_path(), {},
                                     reply_handler=lambda: print('Advertisement registered'),
                                     error_handler=lambda e: print('Failed to register ad:', e))

    mainloop = GLib.MainLoop()
    try:
        mainloop.run()
    except KeyboardInterrupt:
        print("Interrupted by user")
        ad_manager.UnregisterAdvertisement(advertisement.get_path())
        advertisement.remove_from_connection(bus, advertisement.get_path())

if __name__ == '__main__':
    main()
