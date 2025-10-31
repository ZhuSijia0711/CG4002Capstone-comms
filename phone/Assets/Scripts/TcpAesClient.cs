using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Security.Cryptography;
using System.Threading;
using UnityEngine;

public class TcpAesServer : MonoBehaviour
{
    public int listenPort = 6000;

    private TcpListener listener;
    private TcpClient client;
    private NetworkStream stream;
    private Thread listenThread;

    private static readonly byte[] AES_KEY = Encoding.UTF8.GetBytes("1234567890abcdef");
    private static readonly byte[] AES_IV = new byte[16]; // must match Python

    void Start()
    {
        listenThread = new Thread(StartServer);
        listenThread.IsBackground = true;
        listenThread.Start();
    }

    void StartServer()
    {
        try
        {
            listener = new TcpListener(IPAddress.Any, listenPort);
            listener.Start();
            Debug.Log($"🖥️ Unity TCP server listening on port {listenPort}...");

            client = listener.AcceptTcpClient();
            stream = client.GetStream();
            Debug.Log("✅ Python connected to Unity");

            while (client.Connected)
            {
                byte[] buffer = new byte[16];
                int bytesRead = stream.Read(buffer, 0, buffer.Length);
                if (bytesRead > 0)
                {
                    byte[] decrypted = DecryptAES(buffer);
                    string receivedText = Encoding.UTF8.GetString(decrypted).TrimEnd('\0');
                    Debug.Log($"🤖 Received from Python: {receivedText}");
                }
            }
        }
        catch (Exception e)
        {
            Debug.LogError($"❌ Server error: {e.Message}");
        }
    }

    byte[] DecryptAES(byte[] data)
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

    void OnApplicationQuit()
    {
        stream?.Close();
        client?.Close();
        listener?.Stop();
        listenThread?.Abort();
    }
}
