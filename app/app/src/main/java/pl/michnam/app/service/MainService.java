package pl.michnam.app.service;

import android.app.Notification;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.os.Binder;
import android.os.IBinder;
import android.util.Log;

import androidx.annotation.Nullable;
import androidx.core.app.NotificationCompat;

import pl.michnam.app.MainActivity;
import pl.michnam.app.R;
import pl.michnam.app.scan.WifiScan;
import pl.michnam.app.util.Tag;

import static pl.michnam.app.App.CHANNEL_ID;

public class MainService extends Service {
    private static boolean working;

    private ServiceCallbacks serviceCallbacks;
    private final IBinder binder = new LocalBinder();

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        pushServiceForeground();
        return START_NOT_STICKY;
    }

    public void startWifiScan() {
        WifiScan.setupWifiScan(this, serviceCallbacks);
    }

    /////////////////////////////////
    /////// SERVICE UTILS ///////////
    /////////////////////////////////

    public void setServiceCallbacks(ServiceCallbacks serviceCallbacks) {
        this.serviceCallbacks = serviceCallbacks;
    }

    public class LocalBinder extends Binder {
        public MainService getService() {
            return MainService.this;
        }
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return binder;
    }

    private void pushServiceForeground() {
        Intent notificationIntent = new Intent(this, MainActivity.class);
        PendingIntent pendingIntent = PendingIntent.getActivity(this, 0, notificationIntent, 0);
        Notification notification = new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle("You are currently in: area 51")
                .setSmallIcon(R.drawable.flag)
                .setContentIntent(pendingIntent).build();

        startForeground(364, notification);
    }

    ///////////////////////////
    ///// GETTERS SETTERS /////
    ///////////////////////////

    public static boolean isWorking() {
        return working;
    }

    public static void setWorking(boolean working) {
        MainService.working = working;
    }
}