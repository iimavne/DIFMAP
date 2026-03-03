#ifndef mc_h
#define mc_h

#define TRUE 1
#define FALSE 0

double mc(double *input,long *inputsize);
void calcmc(double *out, double z[],long *in);
void sort(double x[],long n, double y[]);
double pull(double a[],long n, long k);
double whimed(double a[],long iw[],long n);
double calwork(double a,double b,long ai,long bi,long ab,double eps);

#endif


