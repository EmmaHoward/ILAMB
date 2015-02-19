import numpy as np
import ilamblib as il
from constants import convert

class CO2MaunaLoa():
    """
    Confront models with the CO2 concentration data from Mauna Loa.
    """
    def __init__(self):

        # Populate with observational data needed for the confrontation
        mml           = np.genfromtxt("../demo/data/monthly_mlo.csv",delimiter=",",skip_header=57)
        self.name     = "CO2MaunaLoa"
        self.t        = (mml[:,3]-1850.)*365. # convert to days since 00:00:00 1/1/1850
        self.var      = np.ma.masked_where(mml[:,4]<0,mml[:,4])
        self.unit     = "1e-6"
        self.lat      = 19.4
        self.lon      = 24.4
        self.nlayers  = 3 

    def getData(self,initial_time=-1e20,final_time=1e20,output_unit=""):
        """Retrieves the confrontation data on the desired time frame and in
        the desired unit.

        Parameters
        ----------
        initial_time : float, optional
            include model results occurring after this time
        final_time : float, optional
            include model results occurring before this time
        output_unit : string, optional
            if specified, will try to convert the units of the variable 
            extract to these units given (see convert in ILAMB.constants)

        Returns
        -------
        t : numpy.ndarray
            a 1D array of times in days since 00:00:00 1/1/1850
        var : numpy.ma.core.MaskedArray
            an array of the extracted variable
        unit : string
            a description of the extracted unit
        """
        begin = np.argmin(np.abs(self.t-initial_time))
        end   = np.argmin(np.abs(self.t-final_time))+1
        if output_unit is not "":
            try:
                self.var *= convert["co2"][output_unit][self.unit]
                self.unit = output_unit
            except:
                raise il.UnknownUnit("Variable is in units of [%s], you asked for [%s] but I do not know how to convert" % (self.unit,output_unit))
        return self.t[begin:end],self.var[begin:end],self.unit

    def confront(self,m):
        r"""Confronts the input model with the observational data.

        This confrontation uses the Mauna Loa CO2 data and compares it
        to model results at that given latutide and longitude. If the
        model has CO2 in mass instead of parts per million, it will
        convert the value. If the CO2 is given at atmospheric levels,
        it will average the first "nlayer" unmasked levels to get a
        single value for each time.

        Parameters
        ----------
        m : ILAMB.ModelResult.ModelResult
            the model results

        Returns
        -------
        cdata : dictionary
            contains all outputs/metrics

        Notes
        -----
        The dictionary key "metric" will return a dictionary which
        contains the analysis results. For this confrontation we
        include the following quantities in the analysis:

        "PeriodMean" : float 
            The mean value of the model result over the time period of
            the observational data
        "MonthlyMeanBias" : float
            The bias of the monthly mean model result compared to the
            observational data in "1e-6"
        "MonthlyMeanRMSE" : float
            The RMSE of the monthly mean model result compared to the
            observational data in "1e-6"
        "MonthlyMeanBiasScore" : float
            The MonthlyMeanBias normalized to dimensionless units on
            [0,1]. See the "score" normalization method of
            ILAMB.ilamblib.Bias
        "MonthlyMeanRMSEScore" : float
            The MonthlyMeanRMSE normalized to dimensionless units on
            [0,1]. See the "score" normalization method of
            ILAMB.ilamblib.RootMeanSquaredError
        "InterannualVariabilityScore" : float
            A dimensionless score comparing the standard deviation of
            the annual amplitudes. If :math:`A_{\text{model}}` is a
            vector of the annual model amplitudes and
            :math:`A_{\text{obs}}` is that of the observations, then
            the interannual variability score is given by

            .. math:: 1-\left|\frac{\sigma(A_{\text{model}})-\sigma(A_{\text{obs}})}{\sigma(A_{\text{obs}})}\right|

            where the score is truncated to be on the [0,1] interval
            and :math:`\sigma` denotes the standard deviation operator.
        """

        # time limits for this confrontation, with a little padding to
        # account for differences in monthly time representations
        t0,tf = self.t.min()-5, self.t.max()+5

        # extract the time, variable, and unit of the model result
        tm,vm,um = m.extractPointTimeSeries("co2",self.lat,self.lon,
                                            initial_time=t0,
                                            final_time=tf,
                                            alt_vars=["co2mass"],
                                            output_unit="1e-6")
        
        # update time limits, might be less model data than observations
        t0,tf = tm.min(), tm.max()

        # get the corresponding observational data on the same time frame
        to,vo,uo = self.getData(initial_time=t0,final_time=tf,output_unit="1e-6")

        # perform some assertion to verify data integrity, are the
        # times within 15 days of each other?
        assert np.allclose(tm,to,atol=15)

        # some CO2 results are given in atmospheric layers, so we need
        # to handle this...
        if vm.ndim == 2:
            # ...however, many of the early layers are masked, so
            # determine which index is the first non-masked
            index = np.apply_along_axis(np.sum,1,vm.mask)

            # now we will average the first nlayers non-masked layers
            tmp = np.zeros(tm.size)
            for i in range(self.nlayers):
                tmp += vm[np.ix_(range(tm.size)),(index+i).clip(0,vm.shape[1])][0,:]
            vm = tmp/self.nlayers

        # now we can do some analysis, the results of which we will
        # load into a dictionary which we return. The
        # plotting/visualization routines are written to operate on
        # this dictionary so its format is important.
        cdata = {}

        # put the extracted model data and manipulations here
        cdata["model"] = {} 
        cdata["model"]["t"] = tm; cdata["model"]["var"] = vm; cdata["model"]["unit"] = um

        # put the observation data and manipulations here
        cdata["obs"] = {} 
        cdata["obs"]["t"] = to; cdata["obs"]["var"] = vo; cdata["obs"]["unit"] = uo
        
        # make a few function aliases to help readibility
        mean = np.ma.average
        bias = il.Bias
        rmse = il.RootMeanSquaredError

        # give each time a weight to be used in the weighted averages below
        mw = il.MonthlyWeights(tm)

        # put the metrics here
        cdata["metric"] = {}
        cdata["metric"]["PeriodMean"]           = mean(vm,weights=mw)
        cdata["metric"]["MonthlyMeanBias"]      = bias(vm,vo,weights=mw)
        cdata["metric"]["MonthlyMeanBiasScore"] = bias(vm,vo,weights=mw,normalize="score")
        cdata["metric"]["MonthlyMeanRMSE"]      = rmse(vm,vo,weights=mw)
        cdata["metric"]["MonthlyMeanRMSEScore"] = rmse(vm,vo,weights=mw,normalize="score")
        vmmin,vmmax = il.AnnualMinMax(tm,vm); stdm = (vmmax-vmmin).std()
        vomin,vomax = il.AnnualMinMax(to,vo); stdo = (vomax-vomin).std()
        cdata["metric"]["InterannualVariabilityScore"] = (1-np.abs((stdm-stdo)/stdo)).clip(0)

        return cdata