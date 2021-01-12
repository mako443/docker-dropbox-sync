import dropbox
from dropbox.exceptions import ApiError
import os
import os.path as osp
import shutil
import os.path as path
import time
import sys
import threading

THREAD_COUNT=4

def process_folder_entries(found_files, found_folders, found_deleted_files, entries):
    for entry in entries:
        if isinstance(entry, dropbox.files.FileMetadata):
            found_files[entry.path_lower]= entry
        elif isinstance(entry, dropbox.files.FolderMetadata):
            found_folders[entry.path_lower]= entry
        elif isinstance(entry, dropbox.files.DeletedMetadata):
            found_deleted_files[entry.path_lower]= entry
            found_files.pop(entry.path_lower, None) # ignore KeyError if missing
            found_folders.pop(entry.path_lower, None) # ignore KeyError if missing

    return found_files, found_folders, found_deleted_files

def remote_path_exists(path):
    try:
        dbx.files_get_metadata(path)
        return True
    except ApiError as e:
        if e.error.get_path().is_not_found():
            return False
        raise    

def gather_remote(remote_path):
    result= dbx.files_list_folder(path=remote_path, recursive=True, include_deleted=True)
    found_files, found_folders, found_deleted_files = process_folder_entries({}, {}, {}, result.entries)
    while result.has_more:
        result = dbx.files_list_folder_continue(result.cursor)
        found_files, found_folders, found_deleted_files = process_folder_entries(found_files, found_folders, found_deleted_files, result.entries)    

    return found_files, found_folders, found_deleted_files

def gather_local(local_path):
    local_files= [osp.join(dp, f) for dp, dn, fn in os.walk(local_path) for f in fn]
    local_folders= [osp.join(dp, d) for dp, dn, fn in os.walk(local_path) for d in dn]
    return local_files, local_folders

#Delete local files if there is corresponding remote DeletedMetadata
#Delete local folders (recursively) if there is not corresponding remote folder entry
def delete_remote2local(local_root, remote_root, verbose=False):
    found_files, found_folders, found_deleted_files= gather_remote(remote_root)
    local_files, local_folders= gather_local(local_root)

    remote_prefix= '/' if len(remote_root)==0 else remote_root

    #Delete files
    for remote_deleted_file in found_deleted_files:
        local_file= osp.join(local_root, remote_deleted_file[len(remote_prefix):])
        if osp.isfile(local_file):
            if verbose: print('Deleting file', local_file)
            os.remove(local_file)

    #Delete folders
    for local_folder in local_folders:
        remote_path= remote_prefix + local_folder[len(local_root):]
        if remote_path not in found_folders:
            #Skip if already deleted
            if osp.isdir(local_folder):
                if verbose: print('Deleting folder', local_folder)
                shutil.rmtree(local_folder)    

def download_file(local_path, remote_file, verbose=False):
    if verbose: print('Downloading file', local_path)
    with open(local_path, 'wb') as f:
        _, res= dbx.files_download(path=remote_file)
        f.write(res.content)

def add_remote2local(local_root, remote_root, verbose=False):
    found_files, found_folders, found_deleted_files= gather_remote(remote_root)
    local_files, local_folders= gather_local(local_root)

    remote_prefix= '/' if len(remote_root)==0 else remote_root

    #Create folders
    for remote_folder in found_folders:
        local_path= osp.join(local_root, remote_folder[len(remote_prefix):])
        if not osp.isdir(local_path):
            if verbose: print('Creating folder', local_path)
            os.mkdir(local_path)


    #Download files (parallel)
    download_files= []

    #Gather files
    for remote_file in found_files:
        local_path= osp.join(local_root, remote_file[len(remote_prefix):])
        if not osp.isfile(local_path) or os.stat(local_path).st_size != found_files[remote_file].size:
            download_files.append((local_path, remote_file))
        else:
            if verbose: print('Skipping file', local_path)

    #Parallel downloads
    threads= []
    for i_step in range(0, len(download_files), THREAD_COUNT):
        for i_thread in range(THREAD_COUNT):
            if i_step+i_thread>=len(download_files):
                break
            threads.append(threading.Thread(target=download_file, args=(download_files[i_step+i_thread][0], download_files[i_step+i_thread][1], verbose)))
            threads[-1].start()
        for t in threads:
            t.join()
        threads= []

def upload_file(local_file, remote_path, verbose=False):
    if verbose: print('Uploading file', remote_path)
    with open(local_file,'rb') as f:
        dbx.files_upload(f.read(), remote_path)

def add_local2remote(local_root, remote_root, verbose=False):
    found_files, found_folders, found_deleted_files= gather_remote(remote_root)
    local_files, local_folders= gather_local(local_root)

    remote_prefix= '/' if len(remote_root)==0 else remote_root

    #Create folders in remote
    for local_folder in local_folders:
        remote_path= remote_prefix + local_folder[len(local_root):]
        if not remote_path_exists(remote_path):
            if verbose: print('Creating remote folder', remote_path)
            dbx.files_create_folder(remote_path)
        else:
            if verbose: print('Skipping folder', remote_path)

    #Upload files to remote (in parallel)
    upload_files= []
    #Gather files
    for local_file in local_files:
        remote_path= remote_prefix + local_file[len(local_root):]
        if remote_path not in found_files:
            upload_files.append((local_file, remote_path))
            # if verbose: print('Uploading file', remote_path)
            # with open(local_file,'rb') as f:
            #     dbx.files_upload(f.read(), remote_path)
        else:
            if verbose: print('Skipping file', remote_path)

    #Parallel uploads
    threads= []
    for i_step in range(0, len(upload_files), THREAD_COUNT):
        for i_thread in range(THREAD_COUNT):
            if i_step+i_thread>=len(upload_files):
                break
            threads.append(threading.Thread(target=upload_file, args=(upload_files[i_step+i_thread][0], upload_files[i_step+i_thread][1], verbose)))
            threads[-1].start()
        for t in threads:
            t.join()
        threads= []    

#Care to use the correct order: delete remote->local first
def sync(local_root, remote_root, verbose=False):
    if not local_root.endswith('/'): local_root= local_root+'/'
    if remote_root=='/': remote_root=""
    assert osp.isdir(local_root)
    print('Syncing', local_root, remote_root)

    while True:
        if verbose: print('Syncing...', flush=True)

        delete_remote2local(local_root, remote_root, verbose)
        add_local2remote(local_root,remote_root, verbose)
        add_remote2local(local_root,remote_root, verbose)

        if verbose: print('Syncing done. \n', flush=True)
        time.sleep(120)
    

if __name__ == "__main__":
    with open(osp.join(osp.dirname(osp.realpath(__file__)), 'token.txt'), 'r') as f:
        token= f.read().strip()

    dbx=dropbox.Dropbox(token)

    print(sys.argv)
    if not (len(sys.argv)==3 or len(sys.argv)==4):
        print('Usage: local_root remote_root [-v]')
        quit()
    sync(sys.argv[1], sys.argv[2], "-v" in sys.argv)
