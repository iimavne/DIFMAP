#include <stdlib.h>
#include <stdio.h>
#include <math.h>

#include "mc.h"


/* Algorithm for the skewness estimator medcouple (MC)
 * 
 * Params:
 * double *input = input array
 * long *inputsize = number of elements in input array
 * 
 * Ouput:
 * medcouple (MC)
*/

double mc(double *input,long *inputsize)
{
  double mc_input,mc_minput,mcvalue;
  double *minput;
  long i,s;
  
  s=*inputsize;
  minput=(double *) malloc((s+1)*sizeof(double));
    
  /* calculate mc(x) */
  calcmc(&mc_input, input, &s);
  /*lprintf(stderr,"\nMC(x)=%lf\n",mc_input);*/
    
  /* create -x array */
  for (i=0;i<s;i++){
    minput[i]=-input[i];
  }

  /* calculate mc(-x) */
  calcmc(&mc_minput, minput, &s);
  /*lprintf(stderr,"MC(-x)=%lf\n",mc_minput);*/
   
  /* calculate the 'real' mc */
  mcvalue=(mc_input-mc_minput)/2.0f;
  
  return mcvalue;
}	

/* Algorithm for actually calculate the medcouple
 * 
 * Params:
 * *out = output medcouple
 * z = input array of double
 * *in = number of elements in z
 * 
*/

void calcmc(double *out, double z[],long *in)
{
  double medc,xmed2,yden,xmed,trial,eps;
  double *work,*y,*x,*y1,*y2;
  long *left,*right,*weight,*q,*p;
  long k,knew,nl,nr,sumq,sump,i,j,jj,IsFound,h1,h2,n;
  n=*in;
  
  y=(double *) malloc((n+1)*sizeof(double));
  x=(double *) malloc((n+1)*sizeof(double));
  y1=(double *) malloc((n+1)*sizeof(double));
  y2=(double *) malloc((n+1)*sizeof(double));
  work=(double *) malloc((n+1)*sizeof(double));
  left=(long *) malloc((n+1)*sizeof(long));
  right=(long *) malloc((n+1)*sizeof(long));
  weight=(long *) malloc((n+1)*sizeof(long));
  q=(long *) malloc((n+1)*sizeof(long));
  p=(long *) malloc((n+1)*sizeof(long));

  eps=0.0000000000001;
  x[0]=0;
  for (i=0;i<n;i++){
    x[i+1]=-z[i];
  }
  xmed=pull(x,n,floor(n/2)+1);
  if (n%2 == 0){
    xmed2=pull(x,n,floor(n/2));
    xmed=(xmed+xmed2)/2;
  }
  for (i=1;i<=n;i++){
    x[i]=x[i]-xmed;
  }
  sort(x,n,y);
/*  if (-y[1] > y[n]){
    yden=-2*y[1];
  }
  else{
    yden=2*y[n];
  }*/
  yden = 1;
  for (i=1;i<=n;i++){
      y[i]=-y[i]/yden;
  }
  j=1;
  while (y[j] > eps){
      y1[j]=y[j];
      j++;
  }
  i=1;
  while (y[j] > -eps){
      y1[j]=y[j];
      y2[i]=y[j];
      j++;
      i++;
  }
  h1=j-1;
  while (j < n+1){
      y2[i]=y[j];
      j++;
      i++;
  }
  h2=i-1;
  for (i=1;i<=h2;i++){
      left[i]=1;
      right[i]=h1;
  }
  nl=0;
  nr=h1*h2;
  knew=floor(nr/2)+1;
  IsFound=FALSE;
  while ((nr-nl>n)& (!IsFound)){
      j=1;
      for (i=1;i<=h2;i++){
        if (left[i]<=right[i]){
          weight[j]=right[i]-left[i]+1;
          k = left[i]+floor(weight[j]/2);
          work[j]=calwork(y1[k],y2[i],k,i,h1+1,eps);
          j++;
         }
      }
      trial=whimed(work,weight,j-1);
      j=1;
      for (i=h2;i>=1;i--){

        while ((j<=h1)&(calwork(y1[j],y2[i],j,i,h1+1,eps)>trial)){
        j++;
        }
        p[i]=j-1;

      }
      j=h1;
      for (i=1;i<=h2;i++){
		  
        while ((j>=1)&(calwork(y1[j],y2[i],j,i,h1+1,eps)<trial)){
          j--;
        }
        q[i]=j+1;
      }
      sump=0;
      sumq=0;
      for (i=1;i<=h2;i++){
        sump=sump+p[i];
        sumq=sumq+q[i]-1;
      }

      if (knew<=sump){
        for (i=1;i<=h2;i++){
          right[i]=p[i];
        }
        nr=sump;
      }
      else{
         if (knew>sumq){
           for (i=1;i<=h2;i++){
             left[i]=q[i];
           }
           nl=sumq;
         }
         else{
           medc=trial;
           IsFound=TRUE;
         }
      }
    } /*end while-lus*/
    if (!IsFound){
      j=1;
      for (i=1;i<=h2;i++){

        if (left[i]<=right[i]){
			
          for (jj=left[i];jj<=right[i];jj++){

             work[j]=-calwork(y1[jj],y2[i],jj,i,h1+1,eps);
             j++;

          }
        }
      }
      medc=pull(work,j-1,knew-nl);
      medc=-medc;
   }
  
  free(y);
  free(x);
  free(y1);
  free(y2);
  free(work);
  free(left);
  free(right);
  free(weight);
  free(p);
  free(q);
  *out=medc;
}


/* Sort
* sort(x,n,y): sorts an array x of length n and stores the result in an array y (of size at least n)
*/
void sort(double a[],long n, double b[])
{
  double xx,amm;
  long i,jss,jndl,jr,jnc,j,jtwe;
  long *jlv,*jrv;

  jlv=(long *) malloc((n+1)*sizeof(long));
  jrv=(long *) malloc((n+1)*sizeof(long));
  for (i=1;i<=n;i++){
    b[i]=a[i];
  }
  jss=1;
  jlv[1]=1;
  jrv[1]=n;
  do{

    jndl=jlv[jss];
    jr=jrv[jss];
    jss=jss-1;
    
    do{
      jnc=jndl;
      j=jr;
      jtwe=floor((jndl+jr)/2);
      xx=b[jtwe];
      
      do{
        while (b[jnc]<xx){
          jnc++;
        }
        while (xx<b[j]){
          j--;
        }
        if (jnc<=j){
          amm=b[jnc];
          b[jnc]=b[j];
          b[j]=amm;
          jnc++;
          j--;
        }
      } while (jnc<=j);
      
      if ((j-jndl)>=(jr-jnc)){
        if (jndl<j){
          jss++;
          jlv[jss]=jndl;
          jrv[jss]=j;
        }
        jndl=jnc;
      }
      else{
        if (jnc<jr){
          jss++;
          jlv[jss]=jnc;
          jrv[jss]=jr;
        }
        jr=j;
      }
    } while (jndl<jr);
  } while (jss!=0);
  
  free(jrv);
  free(jlv);
}

/* Pull
 * pull(a,n,k): finds the k-th order statistic of an array a of length n
*/

double pull(double a[],long n, long k)
{
  double* b;
  double outp,ax,buffer;
  long l,lr,jnc,j,i;

  b=(double *) malloc((n+1)*sizeof(double));
  for (i=1;i<=n;i++){
    b[i]=a[i];
  }
  l=1;
  lr=n;
  while (l<lr){
    ax=b[k];
    jnc=l;
    j=lr;
    while (jnc<=j){
      while (b[jnc]<ax){
        jnc++;
      }
      while (b[j]>ax){
        j--;
      }
      if (jnc<=j){
        buffer=b[jnc];
        b[jnc]=b[j];
        b[j]=buffer;
        jnc++;
        j--;
      }
    }
    if (j<k){
      l=jnc;
    }
    if (k<jnc){
      lr=j;
    }
  }
  outp=b[k];
  free(b);
  
  return(outp);
}

/* whimed(a,iw,n): finds the weighted high median of an array a of length n, using the array iw
(also of length n) with positive longinteger weights.
*/
double whimed(double a[],long iw[],long n)
{
  double* acand;
  double trial,whmed;
  long* iwcand;
  long nn;
  long i,wtotal,wrest,wleft,wmid,wright,kcand,IsFound;

  acand=(double *) malloc((n+1)*sizeof(double));
  iwcand=(long *) malloc((n+1)*sizeof(long));
  nn=n;
  wtotal=0;
  for (i=1;i<=nn;i++){
    wtotal+=iw[i];
  }
  wrest=0;
  IsFound=FALSE;
  while (!IsFound){
    wleft=0;
    wmid=0;
    wright=0;
    trial=pull(a,nn,floor(nn/2)+1);
    for (i=1;i<=nn;i++){
      if (a[i]<trial){
        wleft+=iw[i];
      }
      else{      
        if (a[i]>trial){
          wright+=iw[i];
        }
        else{
          wmid+=iw[i];
        } /*end else 2*/
      } /*end else 1*/
    } /*end for*/
    
    if ((2*wrest+2*wleft)>wtotal){
      kcand=0;
      for (i=1;i<=nn;i++){
        if (a[i]<trial){
          kcand++;
          acand[kcand]=a[i];
          iwcand[kcand]=iw[i];
        }
      }
      nn=kcand;
    }
    else{
      if ((2*wrest+2*wleft+2*wmid) >wtotal){
        whmed=trial;
        IsFound=TRUE;
      }
      else{
        kcand=0;
        for (i=1;i<=nn;i++){
          if (a[i]>trial){
            kcand++;
            acand[kcand]=a[i];
            iwcand[kcand]=iw[i];
          }
        }/*end for*/
        nn=kcand;
        wrest=wrest+wleft+wmid;

      } /*end else 2*/
    } /*end else 1*/
    for(i=1;i<=nn;i++){
      a[i]=acand[i];
      iw[i]=iwcand[i];
    }
  }/*end while*/
  
  free(iwcand);
  free(acand);
  
  return(whmed);
}

/* Calwork
 * calwork(a,b,ai,bi,ab,eps): calculates the values needed to compute the mc
*/

double calwork(double a,double b,long ai,long bi,long ab,double eps)
{
  double cwork;

  if (fabs(a-b) < 2.0*eps){
    if (ai+bi == ab){
        cwork = 0;
    }
    else{
      if (ai+bi < ab){
        cwork = 1;
      }
      else{
        cwork = -1;
      }
    }
  }
  else{
    cwork = (a+b)/(a-b);
  }
    
  return(cwork);
}



