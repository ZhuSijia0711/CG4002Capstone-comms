using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Security.Cryptography;
using System.Threading;
using UnityEngine;
using System.Collections.Concurrent;
using TMPro;

public class TcpAesServer : MonoBehaviour
{
    public int listenPort = 6000;
    public TextMeshProUGUI logText;

    [Header("References")]
    [SerializeField] private CorgiAnimation corgiAnim;   // 🐶 Handles animations + bars
    [SerializeField] private SteakThrower steakThrower;  // 🍖 Handles steak throw
    [SerializeField] private BallThrower ballThrower;    // ⚽ Handles ball throw

    private TcpListener listener;
    private TcpClient client;
    private NetworkStream stream;
    private Thread listenThread;

    private readonly ConcurrentQueue<string> logQueue = new ConcurrentQueue<string>();
    private readonly ConcurrentQueue<int> dataQueue = new ConcurrentQueue<int>();

    private static readonly byte[] AES_KEY = Encoding.UTF8.GetBytes("1234567890abcdef");
    private static readonly byte[] AES_IV = new byte[16];

    private bool serverRunning = true;

    void Start()
    {
        logQueue.Enqueue("✅ TcpAesServer started");
        listenThread = new Thread(ServerLoop);
        listenThread.IsBackground = true;
        listenThread.Start();
    }

    void Update()
    {
        // 🧾 Display the latest log message
        while (logQueue.TryDequeue(out string msg))
        {
            if (logText != null)
            {
                logText.text = msg; // Overwrite the logText with the latest log
            }
            else
            {
                Debug.Log(msg);
            }
        }

        // 🎯 Handle incoming data
        while (dataQueue.TryDequeue(out int value))
        {
            HandleReceivedValue(value);
        }
    }

    private void ServerLoop()
    {
        try
        {
            listener = new TcpListener(IPAddress.Any, listenPort);
            listener.Start();
            logQueue.Enqueue($"🖥 Listening for Python on port {listenPort}...");

            while (serverRunning)
            {
                client = listener.AcceptTcpClient();
                stream = client.GetStream();
                logQueue.Enqueue("✅ Python connected to Unity");

                try
                {
                    byte[] buffer = new byte[16];
                    while (client.Connected)
                    {
                        int bytesRead = stream.Read(buffer, 0, buffer.Length);
                        if (bytesRead == 0)
                        {
                            logQueue.Enqueue("⚠️ Python disconnected.");
                            break;
                        }

                        byte[] decrypted = DecryptAES(buffer);
                        string receivedText = Encoding.UTF8.GetString(decrypted).TrimEnd('\0');

                        logQueue.Enqueue($"🤖 Received from Python: {receivedText}");

                        if (int.TryParse(receivedText, out int value))
                            dataQueue.Enqueue(value);
                    }
                }
                catch (Exception e)
                {
                    logQueue.Enqueue($"⚠️ Connection error: {e.Message}");
                }

                client?.Close();
                stream = null;
                client = null;
                logQueue.Enqueue("🔁 Waiting for Python to reconnect...");
            }
        }
        catch (Exception e)
        {
            logQueue.Enqueue($"❌ Server error: {e.Message}");
        }
    }

    private byte[] DecryptAES(byte[] data)
    {
        using (Aes aes = Aes.Create())
        {
            aes.Key = AES_KEY;
            aes.IV = AES_IV;
            aes.Mode = CipherMode.CBC;
            aes.Padding = PaddingMode.None;
            using (ICryptoTransform decryptor = aes.CreateDecryptor())
            {
                return decryptor.TransformFinalBlock(data, 0, data.Length);
            }
        }
    }
    private void HandleReceivedValue(int value)
    {
        if (!corgiAnim)
        {
            Debug.LogWarning("[TcpAesServer] Missing CorgiAnimation reference!");
            return;
        }

        switch (value)
        {
            case 0:
                logQueue.Enqueue("Stop command received!");
                break;

            case 1:
                logQueue.Enqueue("Come Here command received!");
                corgiAnim.StartRunning();
                break;

            case 2:
                logQueue.Enqueue("Go Away command received!");
                corgiAnim.StartRunning();
                break;

            case 3:
                logQueue.Enqueue("Turn Around command received!");
                corgiAnim.StartRunning();
                break;

            case 4:
                logQueue.Enqueue("🐶 Pet command received!");
                corgiAnim.PlayPetOnce();
                break;

            case 5:
                logQueue.Enqueue("🍖 Feed command received!");
                if (steakThrower)
                    steakThrower.FeedWithThrow(); // 👈 triggers steak + eat animation + hunger restore
                else
                    corgiAnim.PlayEatOnce();      // fallback if no steakThrower linked
                break;

            case 6:
                logQueue.Enqueue("⚽ Ball throw command received!");
                if (ballThrower)
                    ballThrower.ThrowBall();
                else
                    logQueue.Enqueue("⚠️ No BallThrower reference set in Inspector!");
                break;

            default:
                logQueue.Enqueue($"⚙️ Unknown command value: {value}");
                break;
        }
    }

    private void OnApplicationQuit()
    {
        serverRunning = false;
        try
        {
            stream?.Close();
            client?.Close();
            listener?.Stop();
            listenThread?.Interrupt();
        }
        catch { }
    }
}