#include <stdio.h>
#include <stdlib.h>
#include <math.h>

#include "obs.h"
#include "telspec.h"
#include "clphs.h"
#include "logio.h"
#include "vlbconst.h"

/*.......................................................................
 * Determine the goodness of fit between the observed and model
 * visibilities.
 *
 * Input:
 *  ob   Observation * The data set to be examined.
 *  uvmin      float   The minimum UV radius to take visibilities from.
 *  uvmax      float   The maximum UV radius to take visibilities from.
 *  options unsigned   A bitwise union of ModdifOptions (defined in obs.h)
 *                     which indicate which statistics are to be returned.
 *                     The valid values can be any combination of:
 *                       MD_VIS_FIT     - The fit between the model and
 *                                        observed visibilities. This sets
 *                                        md->chisq, md->rms, md->ndata.
 *                       MD_CLPHS_FIT   - The fit between the model and
 *                                        observed closure phases. This sets
 *                                        md->clphs_chisq and md->clphs_nused.
 *                       MD_ALL_OPTIONS - All of the above options.
 *                     Note that md->uvmin and md->uvmax are always set,
 *                     regardless of which options are specified.
 * Input/Output:
 *  md        Moddif * Send a pointer to the container into which to
 *                     place return values.
 * Output:
 *  return       int   0 - OK. You are guaranteed that md->ndata > 0.
 *                     1 - Error. Note that a lack of any useable points
 *                         such as when all points are flagged, is regarded
 *                         as an error.
 */
int moddif(Observation *ob, Moddif *md, float uvmin, float uvmax,
           unsigned options)
{
  int isub;               /* The index of the sub-array being processed */
  int cif;                /* The index of the IF being processed */
  int old_if;             /* State of current IF to be restored on exit */
  long nvis=0;            /* The number of visibilities used. */
  float msd=0.0f;         /* Mean square diff between model and observed data */
  float chi=0.0f;         /* Mean square number of sigma deviation */
  float clphs_chisq=0.0f; /* Closure-phase chi-squared */
  long clphs_nused=0;     /* The number of closure phases in clphs_chisq */
/*
 * Sanity checks.
 */
  if(!ob_ready(ob, OB_SELECT, "moddif"))
    return 1;
  if(md==NULL) {
    lprintf(stderr, "moddif: NULL return container.\n");
    return 1;
  };
/*
 * Store the state of the current IF.
 */
  old_if = get_cif_state(ob);
/*
 * Initialize output values.
 */
  md->ndata = 0;
  md->rms = 0.0f;
  md->chisq = 0.0f;
  md->clphs_chisq = 0.0f;
  md->clphs_nused = 0;
  md->uvmin = 0.0;
  md->uvmax = 0.0;
/*
 * Work out the available UV range.
 */
  {
    UVrange *uvr = uvrange(ob, 1, 0, uvmin, uvmax);
    if(uvr==NULL)
      return 1;
    uvmin = uvr->uvrmin;
    uvmax = uvr->uvrmax;
  };
/*
 * Loop through all sampled IFs.
 */
  for(cif=0; (cif=nextIF(ob, cif, 1, 1)) >= 0; cif++) {
/*
 * Get the next IF.
 */
    if(getIF(ob, cif))
      return 1;
/*
 * Get the fit between the model and observed visibilities?
 */
    if(options & MD_VIS_FIT) {
/*
 * Visit each subarray in turn.
 */
      for(isub=0; isub<ob->nsub; isub++) {
        Subarray *sub = &ob->sub[isub];
        int ut;
        for(ut=0; ut<sub->ntime; ut++) {
          Visibility *vis = sub->integ[ut].vis;
          int base;
/*
 * Accumulate the baseline based statistics.
 */
          for(base=0; base<sub->nbase; base++,vis++) {
/*
 * Get the square of the UV radius.
 */
            float uu = vis->u * ob->stream.uvscale;
            float vv = vis->v * ob->stream.uvscale;
            float uvrad = sqrt(uu*uu+vv*vv);
/*
 * Only look at unflagged visibilities within the requested UV range.
 */
            if(!vis->bad && uvrad >= uvmin && uvrad <= uvmax) {
/*
 * Calculate the square modulus of the complex difference vector using the
 * cosine rule.
 */
              float ampvis = vis->amp;
              float phsvis = vis->phs;
              float ampmod = vis->modamp;
              float phsmod = vis->modphs;
              float sqrmod = ampvis*ampvis + ampmod*ampmod -
                2.0f * ampvis*ampmod * cos(phsvis-phsmod);
/*
 * Count the number of visibilities used.
 */
              nvis++;
/*
 * Accumulate chi-squared.
 * vis->wt is the reciprocal of the ampitude variance.
 */
              chi += vis->wt * sqrmod;
/*
 * Accumulate the mean-square-difference between model and data.
 */
              msd += (sqrmod - msd) / nvis;
            };
          };
        };
      };
    }
/*
 * Accumulate the closure-phase based statistics in a separate nested
 * loop. This is more efficient than doing it inside the above loops,
 * because it iterates over the closure triangles only once, which
 * is an expensive operation.
 */
    if(options & MD_CLPHS_FIT) {
      Findop oper = FIND_FIRST;  /* Start with finding the first triangle */
      int waserr;                /* Error status from next_tri() */
/*
 * Initialize the closure-triangle iterator.
 */
      Trispec *ts = read_Trispec(ob, "", NULL, 0);
      if(!ts)
        return 1;
/*
 * Iterate over all unique closure triangles in all subarrays over all
 * integrations.
 */
      while((waserr=next_tri(ob, oper, 1, 0, 0, 0, 0, ts)) == 0) {
        Subarray *sub = ob->sub + ts->isub;
        int ut;
        for(ut=0; ut<sub->ntime; ut++) {
          Clphs *cp = get_clphs(ts, sub->integ[ut].vis);
          if(!cp->bad) {
            float dcp = cp->ophs - cp->mphs;  /* Closure phase (obs - model) */
#if 1
/*
 * Wrap the difference into the range -pi to pi.
 */
            dcp -= twopi*floor(dcp / twopi + 0.5);
/*
 * Accumulate the closure-phase chi-squared.
 */
            clphs_chisq += cp->wt * dcp * dcp;
#else
/*
 * Use EHT's definition of the closure-phase chi-squared. Instead of using
 * Sum(|closure_phase_difference|^2 / closure_phase_variance), they
 * use Sum(2*(1-cos(closure_phase_difference))/closure_phase_variance), because
 * unlike the exact calculation of the chi-squared, this has a
 * continuous second derivative at the point where the phase wraps at +/-pi.
 * Note that a taylor expansions shows that:
 *    2*(1-cos(x)) ~= x^2 - x^4/12 + x^6/360 ...
 * So for small angles this approximates x^2, as required to approximate the
 * true chi-squared at the minimum of chi-squared.
 */
            clphs_chisq += 2.0 * cp->wt * (1.0 - cos(dcp));
#endif
            clphs_nused++;
          }
        }
/*
 * On the second and subsequent iterations of the loop, step to the
 * next triangle rather than initializing the iterator.
 */
        oper = FIND_NEXT;
      }
    }
  };
/*
 * Set up return values.
 */
  md->uvmin = uvmin;
  md->uvmax = uvmax;
  md->ndata = 2L * nvis;      /* Count real + imaginary as two measurements */
  md->rms = sqrt(fabs(msd));
  md->chisq = fabs(chi);
  md->clphs_chisq = fabs(clphs_chisq);
  md->clphs_nused = clphs_nused;
/*
 * Reinstate the original IF.
 */
  if(set_cif_state(ob, old_if))
    return 1;
  return 0;
}
