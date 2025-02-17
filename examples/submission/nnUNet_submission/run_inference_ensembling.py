import shutil

if __name__ == '__main__':
    """
    This inference script is intended to be used within a Docker container as part of the KiTS Test set submission. It
    expects to find input files (.nii.gz) in /input and will write the segmentation output to /output
    
    For testing purposes we set the paths to something local, but once we pack it in a docker we need to adapt them of 
    course
    
    IMPORTANT: This script performs inference using two nnU-net configurations, 3d_lowres and 3d_fullres. Within the 
    /parameter folder, this script expects to find a 3d_fullres and a 3d_lowres subfolder. Within each of these there 
    should be fold_X subfolders where X is the fold ID (typically [0-4]). These fold folder CANNOT originate from 
    different configurations (the fullres folds go into the 3d_fullres subfolder, the lowres folds go into the 
    3d_lowres folder!). There also needs to be the plans.pkl file that you find along with these fold_X folders in the 
    corresponding nnunet training output directory.
    
    /parameters/
        3d_fullres/
        ├── fold_0
        │    ├── model_final_checkpoint.model
        │    └── model_final_checkpoint.model.pkl
        ├── fold_1
        ├── ...
        └── plans.pkl
        3d_lowres/
        ├── fold_0
        ├── fold_1
        ├── ...
        └── plans.pkl
    
    Note: nnU-Net will read the correct nnU-Net trainer class from the plans.pkl file. Thus there is no need to 
    specify it here.
    """

    # this will be changed to /input for the docker
    input_folder = '/input'

    # this will be changed to /output for the docker
    output_folder = '/output'

    # this will be changed to /parameters/X for the docker
    parameter_folder_fullres = '/parameters_ensembling/3d_fullres'
    parameter_folder_lowres = '/parameters_ensembling/3d_lowres'

    from nnunet.inference.predict import predict_cases
    from batchgenerators.utilities.file_and_folder_operations import subfiles, join, maybe_mkdir_p

    input_files = subfiles(input_folder, suffix='.nii.gz', join=False)

    # in the parameters folder are five models (fold_X) traines as a cross-validation. We use them as an ensemble for
    # prediction
    folds_fullres = (0, 1, 2, 3, 4)
    folds_lowres = (0, 1, 2, 3, 4)

    # setting this to True will make nnU-Net use test time augmentation in the form of mirroring along all axes. This
    # will increase inference time a lot at small gain, so we turn that off here (you do whatever you want)
    do_tta = False

    # does inference with mixed precision. Same output, twice the speed on Turing and newer. It's free lunch!
    mixed_precision = True

    # This will make nnU-Net save the softmax probabilities. We need them for ensembling the configurations. Note
    # that ensembling the 5 folds of each configurationis done BEFORE saving the softmax probabilities
    save_npz = True

    # predict with 3d_lowres
    output_folder_lowres = join(output_folder, '3d_lowres')
    maybe_mkdir_p(output_folder_lowres)
    output_files_lowres = [join(output_folder_lowres, i) for i in input_files]

    predict_cases(parameter_folder_lowres, [[join(input_folder, i)] for i in input_files], output_files_lowres, folds_lowres,
                  save_npz=save_npz, num_threads_preprocessing=2, num_threads_nifti_save=2, segs_from_prev_stage=None,
                  do_tta=do_tta, mixed_precision=mixed_precision, overwrite_existing=True, all_in_gpu=False,
                  step_size=0.5)

    # predict with 3d_fullres
    output_folder_fullres = join(output_folder, '3d_fullres')
    maybe_mkdir_p(output_folder_fullres)
    output_files_fullres = [join(output_folder_fullres, i) for i in input_files]

    predict_cases(parameter_folder_fullres, [[join(input_folder, i)] for i in input_files], output_files_fullres, folds_fullres,
                  save_npz=save_npz, num_threads_preprocessing=2, num_threads_nifti_save=2, segs_from_prev_stage=None,
                  do_tta=do_tta, mixed_precision=mixed_precision, overwrite_existing=True, all_in_gpu=False,
                  step_size=0.5)

    # ensemble
    from nnunet.inference.ensemble_predictions import merge
    merge((output_folder_fullres, output_folder_lowres), output_folder, 4, override=True, postprocessing_file=None,
          store_npz=False)

    # cleanup
    shutil.rmtree(output_folder_fullres)
    shutil.rmtree(output_folder_lowres)

    # done!

