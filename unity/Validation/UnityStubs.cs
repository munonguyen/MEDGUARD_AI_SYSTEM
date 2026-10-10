// SIGNATURE STUBS for compiler checks outside Unity. Never put under Assets.
// These do not emulate Unity, animation evaluation, audio, networking or meshes.
using System;
using System.Collections;
namespace UnityEngine
{
    public class Object { public static void Destroy(Object value) {} }
    public class MonoBehaviour : Object
    {
        public T GetComponent<T>() where T : new() => new T();
        public Coroutine StartCoroutine(IEnumerator value) => null;
        public void StopAllCoroutines() {}
    }
    public class Coroutine {}
    public class ScriptableObject : Object {}
    public class Transform : Object { public Vector3 localPosition, position; public Vector3 right = new Vector3(1,0,0), up = Vector3.up; }
    public class AnimationClip : Object { public float length = 1; }
    public struct Vector2
    {
        public float x,y; public static Vector2 zero => default;
        public static Vector2 operator *(Vector2 a,float b) => new Vector2 {x=a.x*b,y=a.y*b};
    }
    public struct Vector3
    {
        public float x,y,z;
        public Vector3(float x,float y,float z) {this.x=x;this.y=y;this.z=z;}
        public static Vector3 up => new Vector3(0,1,0);
        public static Vector3 zero => default;
        public static Vector3 operator +(Vector3 a,Vector3 b) => new Vector3(a.x+b.x,a.y+b.y,a.z+b.z);
        public static Vector3 operator -(Vector3 a,Vector3 b) => new Vector3(a.x-b.x,a.y-b.y,a.z-b.z);
        public static Vector3 operator *(Vector3 a,float b) => new Vector3(a.x*b,a.y*b,a.z*b);
        public static Vector3 operator *(float b,Vector3 a) => a*b;
        public static Vector3 operator /(Vector3 a,float b) => a*(1/b);
        public static Vector3 Lerp(Vector3 a,Vector3 b,float t) => a+(b-a)*t;
        public static float Distance(Vector3 a,Vector3 b) {var v=a-b;return (float)Math.Sqrt(v.x*v.x+v.y*v.y+v.z*v.z);}
    }
    public static class Mathf
    {
        public const float PI = (float)Math.PI, Infinity = float.PositiveInfinity;
        public static float Min(float a,float b) => Math.Min(a,b);
        public static float Max(float a,float b) => Math.Max(a,b);
        public static float Sqrt(float x) => (float)Math.Sqrt(x);
        public static float Clamp(float x,float min,float max) => Math.Clamp(x,min,max);
        public static float Clamp01(float x) => Clamp(x,0,1);
        public static float Sin(float x) => (float)Math.Sin(x);
        public static float Exp(float x) => (float)Math.Exp(x);
        public static float Lerp(float a,float b,float t) => a+(b-a)*t;
        public static float SmoothDamp(float a,float b,ref float v,float t,float max,float dt) => a;
    }
    public static class Random { public static float Range(float a,float b)=>a; public static Vector2 insideUnitCircle => default; }
    public static class Time { public static float unscaledTime, unscaledDeltaTime, realtimeSinceStartup; }
    public class Mesh { public int GetBlendShapeIndex(string name) => -1; }
    public class SkinnedMeshRenderer : Object
    { public Mesh sharedMesh; public float GetBlendShapeWeight(int index)=>0; public void SetBlendShapeWeight(int index,float weight){} }
    public class Animator : Object
    {
        public int layerCount = 2;
        public static int StringToHash(string value)=>0;
        public bool HasState(int layer,int state)=>true;
        public void CrossFadeInFixedTime(int state,float duration,int layer,float offset){}
        public void SetLayerWeight(int layer,float weight){}
    }
    public enum AudioDataLoadState {Unloaded,Loading,Loaded,Failed}
    public enum AudioType {MPEG}
    public class AudioClip : Object { public float length; public int samples,frequency; public AudioDataLoadState loadState; }
    public class AudioSource : Object
    {
        public bool isPlaying,playOnAwake,loop,mute;
        public float pitch,spatialBlend,volume=1;
        public int timeSamples; public AudioClip clip;
        public void Stop(){} public void Play(){} public void Pause(){} public void UnPause(){} public void PlayScheduled(double time){}
        public void GetOutputData(float[] data,int channel){}
    }
    public static class AudioSettings { public static double dspTime; }
    public static class AudioListener {public static bool pause;public static float volume=1;}
    public static class JsonUtility {public static string ToJson(object value)=>""; public static T FromJson<T>(string json)=>default;}
    public class CreateAssetMenuAttribute : Attribute { public string menuName; }
    public class RequireComponentAttribute : Attribute {public RequireComponentAttribute(Type t){}}
    public class DefaultExecutionOrderAttribute : Attribute {public DefaultExecutionOrderAttribute(int x){}}
    public class RangeAttribute : Attribute {public RangeAttribute(float a,float b){}}
    public class MinAttribute : Attribute {public MinAttribute(float a){}}
}
namespace UnityEngine.Networking
{
    public class DownloadHandler {public string text;}
    public class DownloadHandlerBuffer : DownloadHandler {}
    public class DownloadHandlerAudioClip : DownloadHandler
    {public bool streamAudio;public static UnityEngine.AudioClip GetContent(UnityWebRequest request)=>null;}
    public class UploadHandlerRaw {public UploadHandlerRaw(byte[] bytes){}}
    public class UnityWebRequest : IDisposable
    {
        public enum Result {InProgress,Success,ConnectionError,ProtocolError,DataProcessingError}
        public string method; public int timeout;public long responseCode;
        public UploadHandlerRaw uploadHandler;public DownloadHandler downloadHandler;public Result result;
        public UnityWebRequest(string url,string method){}
        public void SetRequestHeader(string name,string value){} public string GetResponseHeader(string name)=>null;
        public object SendWebRequest()=>null; public void Abort(){} public void Dispose(){}
    }
    public static class UnityWebRequestMultimedia
    {public static UnityWebRequest GetAudioClip(string url,UnityEngine.AudioType type)=>new UnityWebRequest(url,"GET");}
}
