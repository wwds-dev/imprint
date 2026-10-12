/* A no-op libEGL.so.1, so PySide6's libQt6Gui can load in the Cowork sandbox.

   The sandbox has no Mesa and cannot apt-get it, and libEGL.so.1 is the one
   library libQt6Gui links that is missing. Under QT_QPA_PLATFORM=offscreen Qt
   never calls into EGL, so every entry point here just fails cleanly. Build
   and use (tests/TEST_PLAN.md, Appendix B):

       gcc -shared -fPIC -Wl,-soname,libEGL.so.1 -o $HOME/egl-stub/libEGL.so.1 tests/sandbox/egl_stub.c
       LD_LIBRARY_PATH=$HOME/egl-stub QT_QPA_PLATFORM=offscreen python -m pytest -q ...

   Layout numbers differ from the Mac (Linux fonts), so the sandbox is a
   regression signal, not the release gate. */
typedef void *EGLDisplay; typedef void *EGLConfig; typedef void *EGLContext;
typedef void *EGLSurface; typedef int EGLint; typedef unsigned EGLBoolean; typedef unsigned EGLenum;
EGLBoolean eglBindAPI(EGLenum a){return 0;}
EGLBoolean eglChooseConfig(EGLDisplay d,const EGLint*a,EGLConfig*c,EGLint s,EGLint*n){if(n)*n=0;return 0;}
EGLContext eglCreateContext(EGLDisplay d,EGLConfig c,EGLContext s,const EGLint*a){return 0;}
EGLSurface eglCreatePbufferSurface(EGLDisplay d,EGLConfig c,const EGLint*a){return 0;}
EGLBoolean eglDestroyContext(EGLDisplay d,EGLContext c){return 0;}
EGLBoolean eglDestroySurface(EGLDisplay d,EGLSurface s){return 0;}
EGLBoolean eglGetConfigAttrib(EGLDisplay d,EGLConfig c,EGLint a,EGLint*v){return 0;}
EGLBoolean eglGetConfigs(EGLDisplay d,EGLConfig*c,EGLint s,EGLint*n){if(n)*n=0;return 0;}
EGLContext eglGetCurrentContext(void){return 0;}
EGLDisplay eglGetCurrentDisplay(void){return 0;}
EGLSurface eglGetCurrentSurface(EGLint r){return 0;}
EGLint eglGetError(void){return 0x3000;}
void (*eglGetProcAddress(const char*p))(void){return 0;}
EGLBoolean eglMakeCurrent(EGLDisplay d,EGLSurface a,EGLSurface b,EGLContext c){return 0;}
EGLBoolean eglQueryContext(EGLDisplay d,EGLContext c,EGLint a,EGLint*v){return 0;}
const char*eglQueryString(EGLDisplay d,EGLint n){return 0;}
EGLBoolean eglSwapBuffers(EGLDisplay d,EGLSurface s){return 0;}
EGLBoolean eglSwapInterval(EGLDisplay d,EGLint i){return 0;}
EGLDisplay eglGetDisplay(void*n){return 0;}
EGLBoolean eglInitialize(EGLDisplay d,EGLint*a,EGLint*b){return 0;}
EGLBoolean eglTerminate(EGLDisplay d){return 0;}
EGLBoolean eglGetPlatformDisplayEXT(void){return 0;}
void*eglGetPlatformDisplay(unsigned p,void*n,const long*a){return 0;}
EGLBoolean eglQuerySurface(EGLDisplay d,EGLSurface s,EGLint a,EGLint*v){return 0;}
EGLBoolean eglSurfaceAttrib(EGLDisplay d,EGLSurface s,EGLint a,EGLint v){return 0;}
EGLSurface eglCreateWindowSurface(EGLDisplay d,EGLConfig c,void*w,const EGLint*a){return 0;}
EGLBoolean eglReleaseThread(void){return 0;}
EGLBoolean eglWaitClient(void){return 0;}
EGLBoolean eglWaitNative(EGLint e){return 0;}
